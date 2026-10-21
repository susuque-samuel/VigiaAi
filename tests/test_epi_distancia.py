import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import cv2  # Inicializa a extensão antes de simular módulos; não recarrega DLLs entre casos.
import numpy as np

from epi_inferencia import extrair_deteccoes_epi, reanalisar_epi_por_pessoa, regiao_epi
from epi_monitoramento import MotorAlertas
from main import Monitor

CAIXA = (100, 100, 300, 500)
TAMANHO = (720, 1280, 3)


def pontos_visiveis():
    return {0: (0.5, 0.12, 1), 2: (0.4, 0.1, 1), 5: (0.6, 0.1, 1),
            11: (0.3, 0.3, 1), 12: (0.7, 0.3, 1),
            23: (0.35, 0.65, 1), 24: (0.65, 0.65, 1),
            15: (0.2, 0.6, 1), 16: (0.8, 0.6, 1),
            19: (0.2, 0.65, 1), 20: (0.8, 0.65, 1)}


class ModeloFake:
    names = {0: "capacete", 1: "oculos", 2: "colete"}

    def __init__(self, deteccoes=(), falha=False):
        self.deteccoes = deteccoes
        self.falha = falha
        self.chamadas = []

    def __call__(self, imagem, **opcoes):
        self.chamadas.append((imagem.shape, opcoes))
        if self.falha:
            raise RuntimeError("falha simulada do recorte")
        caixas, classes, confiancas = [], [], []
        for caixa, classe, conf in self.deteccoes:
            caixas.append(caixa)
            classes.append(classe)
            confiancas.append(conf)
        return [SimpleNamespace(names=self.names, boxes=SimpleNamespace(
            xyxy=np.array(caixas), cls=np.array(classes), conf=np.array(confiancas),
        ))]


class TestInferenciaLocal(unittest.TestCase):
    def setUp(self):
        self.quadro = np.zeros(TAMANHO, dtype=np.uint8)

    def avaliar(self, modelo, globais=(), caixas=None, limite=4, rodada=0):
        caixas = [CAIXA] if caixas is None else caixas
        pontos = [pontos_visiveis() for _ in caixas]
        locais, resumo = reanalisar_epi_por_pessoa(
            modelo, self.quadro, caixas, pontos, ["capacete"], list(globais), limite=limite, rodada=rodada,
        )
        return locais, resumo, pontos

    def estado(self, pontos, deteccoes, caixas=None, obrigatorios=None):
        caixas = [CAIXA] if caixas is None else caixas
        obrigatorios = ["capacete"] if obrigatorios is None else obrigatorios
        motor = MotorAlertas()
        for agora in (0, 1.5, 3):
            pessoas, alertas = motor.avaliar(
                caixas, pontos, deteccoes, obrigatorios, set(obrigatorios), TAMANHO, agora,
            )
        return pessoas, alertas

    def test_converte_coordenadas_sem_abaixar_limiar_de_presenca(self):
        modelo = ModeloFake([((80, 20, 160, 70), 0, 0.7)])
        locais, resumo, pontos = self.avaliar(modelo)
        self.assertEqual(locais[0]["caixa"], (168, 108, 248, 158))
        self.assertEqual(modelo.chamadas[0][0], (424, 224, 3))
        self.assertEqual(modelo.chamadas[0][1]["imgsz"], 640)
        self.assertEqual(modelo.chamadas[0][1]["classes"], [0])
        self.assertEqual(resumo["concluidas"], 1)
        pessoas, alertas = self.estado(pontos, locais)
        self.assertEqual(pessoas[0]["epis"]["capacete"], "presente")
        self.assertFalse(alertas)

    def test_indicio_fraco_local_fica_inconclusivo(self):
        locais, _, pontos = self.avaliar(ModeloFake([((80, 20, 160, 70), 0, 0.35)]))
        pessoas, alertas = self.estado(pontos, locais)
        self.assertEqual(pessoas[0]["epis"]["capacete"], "inconclusivo")
        self.assertFalse(alertas)

    def test_positivo_global_evitar_reanalise_desnecessaria(self):
        modelo = ModeloFake()
        global_ = {"classe": "capacete", "caixa": (150, 105, 250, 155), "confianca": 0.8}
        _, resumo, _ = self.avaliar(modelo, [global_])
        self.assertEqual(resumo["concluidas"], 0)
        self.assertFalse(modelo.chamadas)

    def test_falha_local_nao_vira_ausencia(self):
        locais, resumo, pontos = self.avaliar(ModeloFake(falha=True))
        self.assertEqual(resumo["erros"], ["RuntimeError"])
        pessoas, alertas = self.estado(pontos, locais)
        self.assertEqual(pessoas[0]["epis"]["capacete"], "inconclusivo")
        self.assertFalse(alertas)

    def test_limite_de_recortes_deixa_pendencias_inconclusivas(self):
        caixas = [CAIXA, (500, 100, 700, 500)]
        modelo = ModeloFake()
        locais, resumo, pontos = self.avaliar(modelo, caixas=caixas, limite=1)
        self.assertEqual(len(modelo.chamadas), 1)
        self.assertEqual(resumo["pendentes"], 1)
        pessoas, alertas = self.estado(pontos, locais, caixas)
        self.assertEqual(pessoas[0]["epis"]["capacete"], "possivel_ausencia")
        self.assertEqual(pessoas[1]["epis"]["capacete"], "inconclusivo")
        self.assertEqual([a["pessoa_id"] for a in alertas], [1])

    def test_rodizio_avalia_a_proxima_pessoa(self):
        caixas = [CAIXA, (500, 100, 700, 500)]
        _, _, pontos = self.avaliar(ModeloFake(), caixas=caixas, limite=1, rodada=1)
        self.assertFalse(pontos[0]["_epi_local_avaliados"])
        self.assertIn("capacete", pontos[1]["_epi_local_avaliados"])

    def test_previsao_sobre_vizinho_fora_da_caixa_e_descartada(self):
        locais, _, _ = self.avaliar(ModeloFake([((215, 20, 223, 70), 0, 0.9)]))
        self.assertFalse(locais)

    def test_classe_nao_solicitada_e_descartada(self):
        locais, _, _ = self.avaliar(ModeloFake([((80, 20, 160, 70), 2, 0.9)]))
        self.assertFalse(locais)

    def test_cabeca_pequena_nao_comprova_ausencia(self):
        locais, _, pontos = self.avaliar(ModeloFake())
        pontos[0].update({2: (0.49, 0.1, 1), 5: (0.51, 0.1, 1)})
        pessoas, alertas = self.estado(pontos, locais)
        self.assertEqual(pessoas[0]["epis"]["capacete"], "inconclusivo")
        self.assertFalse(alertas)

    def test_maos_pequenas_nao_comprovam_ausencia_de_luvas(self):
        pontos = [pontos_visiveis()]
        pontos[0].update({19: (0.2, 0.605, 1), 20: (0.8, 0.605, 1)})
        pessoas, alertas = self.estado(pontos, [], obrigatorios=["luvas"])
        self.assertEqual(pessoas[0]["epis"]["luvas"], "inconclusivo")
        self.assertFalse(alertas)

    def test_corpo_pequeno_nao_comprova_ausencia_de_colete(self):
        pontos = [pontos_visiveis()]
        pontos[0].update({11: (0.49, 0.3, 1), 12: (0.51, 0.3, 1)})
        pessoas, alertas = self.estado(pontos, [], obrigatorios=["colete"])
        self.assertEqual(pessoas[0]["epis"]["colete"], "inconclusivo")
        self.assertFalse(alertas)

    def test_margem_limitada_a_imagem(self):
        self.assertEqual(regiao_epi((0, 0, 1280, 720), TAMANHO), (0, 0, 1280, 720))

    def test_nan_na_predicao_nao_entra_na_associacao(self):
        modelo = ModeloFake([((80, 20, 160, 70), 0, float("nan"))])
        self.assertFalse(extrair_deteccoes_epi(modelo(self.quadro)))


class TestIntegracaoReanalise(unittest.TestCase):
    def test_falha_local_preserva_quedas_e_globais_reiniciam_filtro_de_classes(self):
        for falha in (False, True):
            with self.subTest(falha=falha), tempfile.TemporaryDirectory() as pasta:
                monitor = Monitor(base=Path(pasta), modelo_epi=Path(pasta) / "teste-epi.pt", modelo_oculos=None)
                monitor.epi_obrigatorio = ["capacete"]
                monitor.motor.confirmacao_queda = 2
                monitor.status["executando"] = True
                globais = []
                relogio = [0.0]

                class Camera:
                    leituras = 0

                    def isOpened(self):
                        return True

                    def read(self):
                        self.leituras += 1
                        if self.leituras <= 3:
                            return True, np.zeros(TAMANHO, dtype=np.uint8)
                        monitor.stop.set()
                        return False, None

                    def release(self):
                        pass

                class PessoaModelo:
                    def __call__(self, *_args, **_kwargs):
                        relogio[0] += 1
                        return [SimpleNamespace(boxes=SimpleNamespace(xyxy=np.array([CAIXA])))]

                class EpiModelo(ModeloFake):
                    def __call__(self, imagem, **opcoes):
                        if imagem.shape == TAMANHO:
                            globais.append(opcoes)
                            return ModeloFake()(imagem)
                        return super().__call__(imagem, **opcoes)

                class Pose:
                    def __enter__(self):
                        return self

                    def __exit__(self, *_):
                        pass

                    def process(self, _imagem):
                        marcos = [SimpleNamespace(x=0, y=0, visibility=0) for _ in range(33)]
                        for i, x, y in ((11, 0.2, 0.4), (12, 0.3, 0.4), (23, 0.7, 0.45), (24, 0.8, 0.45)):
                            marcos[i] = SimpleNamespace(x=x, y=y, visibility=1)
                        return SimpleNamespace(pose_landmarks=SimpleNamespace(landmark=marcos))

                modelo_epi = EpiModelo([((80, 20, 160, 70), 0, 0.8)], falha=falha)
                mp = SimpleNamespace(solutions=SimpleNamespace(pose=SimpleNamespace(Pose=lambda **_: Pose())))
                with patch("main.abrir_camera", return_value=Camera()), patch("main.time", SimpleNamespace(
                    monotonic=lambda: relogio[0]
                )), patch.dict("sys.modules", {
                    "mediapipe": mp, "ultralytics": SimpleNamespace(
                        YOLO=lambda caminho: modelo_epi if Path(caminho).name == "teste-epi.pt" else PessoaModelo()
                    ),
                }), patch.object(monitor, "alerta") as alerta:
                    monitor.executar()
                self.assertEqual(monitor.status["estado"], "parado", monitor.status["mensagem"])
                self.assertEqual(len(globais), 3)
                self.assertTrue(all("classes" in opcoes and opcoes["classes"] is None for opcoes in globais))
                self.assertTrue(all(opcoes["imgsz"] == 640 for opcoes in globais))
                self.assertTrue(any(c.args[1]["tipo"] == "queda" for c in alerta.call_args_list))
                esperado = "inconclusivo" if falha else "presente"
                self.assertEqual(monitor.status["deteccoes"][0]["epis"]["capacete"], esperado)


if __name__ == "__main__":
    unittest.main()
