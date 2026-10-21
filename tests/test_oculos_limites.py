"""Não confundir falha do detector, detalhe insuficiente e presença positiva."""

import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from epi_inferencia import reanalisar_epi_por_pessoa
from epi_monitoramento import MIN_OLHOS_AUSENCIA_OCULOS, MotorAlertas, rotulo_monitoramento
from test_epi_distancia import CAIXA, TAMANHO, ModeloFake, pontos_visiveis
from main import Monitor


def pontos_olhos(distancia=64):
    pontos = pontos_visiveis()
    meia_distancia = distancia / (2 * (CAIXA[2] - CAIXA[0]))
    pontos.update({2: (0.5-meia_distancia, 0.1, 1), 5: (0.5+meia_distancia, 0.1, 1)})
    return pontos


class TestDetalheOculos(unittest.TestCase):
    def avaliar(self, pontos, deteccoes=()):
        motor = MotorAlertas()
        for agora in (0, 1.5, 3):
            pessoas, alertas = motor.avaliar([CAIXA], [pontos], list(deteccoes), ["oculos"],
                                            {"oculos"}, TAMANHO, agora)
        return pessoas[0], alertas

    def test_olhos_pequenos_na_imagem_original_nao_confirmam_ausencia(self):
        for distancia in (12, 44.5, 46.9, MIN_OLHOS_AUSENCIA_OCULOS - 0.1):
            with self.subTest(distancia=distancia):
                pessoa, alertas = self.avaliar(pontos_olhos(distancia))
                self.assertEqual(pessoa["epis"]["oculos"], "inconclusivo")
                self.assertIn("imagem original", pessoa["epis_motivos"]["oculos"])
                self.assertFalse(alertas)

    def test_limite_operacional_inclusivo_permite_observar_nao_e_presenca(self):
        pessoa, alertas = self.avaliar(pontos_olhos(MIN_OLHOS_AUSENCIA_OCULOS))
        self.assertEqual(pessoa["epis"]["oculos"], "possivel_ausencia")
        self.assertEqual(len(alertas), 1)
        self.assertFalse(pessoa["epis_motivos"])

    def test_presenca_forte_continua_valida_abaixo_do_limite_de_ausencia(self):
        pessoa, alertas = self.avaliar(pontos_olhos(30), [{
            "classe": "oculos", "confianca": .8, "caixa": (170, 130, 230, 150),
        }])
        self.assertEqual(pessoa["epis"]["oculos"], "presente")
        self.assertFalse(alertas)

    def test_auxiliar_indisponivel_nao_confirmar_ausencia(self):
        pontos = pontos_olhos()
        pontos["_oculos_aux_indisponivel"] = True
        pessoa, alertas = self.avaliar(pontos)
        self.assertEqual(pessoa["epis"]["oculos"], "inconclusivo")
        self.assertIn("auxiliar", pessoa["epis_motivos"]["oculos"])
        self.assertFalse(alertas)

    def test_detalhe_insuficiente_interrompe_confirmacao_antiga(self):
        motor = MotorAlertas()
        for agora, distancia in ((0, 64), (1.5, 64), (2, 44), (3.5, 64)):
            pessoas, alertas = motor.avaliar([CAIXA], [pontos_olhos(distancia)], [], ["oculos"],
                                            {"oculos"}, TAMANHO, agora)
            self.assertFalse(alertas)
        self.assertEqual(pessoas[0]["epis"]["oculos"], "observando")


class TestRecorteAuxiliar(unittest.TestCase):
    def avaliar(self, principal, auxiliar, deteccoes=(), obrigatorios=None):
        pontos = [pontos_olhos()]
        novas, resumo = reanalisar_epi_por_pessoa(
            principal, np.zeros(TAMANHO, dtype=np.uint8), [CAIXA], pontos,
            ["oculos"] if obrigatorios is None else obrigatorios, list(deteccoes), modelo_oculos=auxiliar,
        )
        return novas, resumo, pontos[0]

    def test_auxiliar_usa_recorte_e_somente_oculos(self):
        auxiliar = ModeloFake([((80, 40, 144, 64), 1, .8), ((80, 20, 160, 70), 0, .9)])
        novas, resumo, pontos = self.avaliar(ModeloFake(), auxiliar)
        self.assertEqual(auxiliar.chamadas[0][0], (424, 224, 3))
        self.assertEqual(auxiliar.chamadas[0][1]["classes"], [1])
        self.assertEqual(auxiliar.chamadas[0][1]["imgsz"], 640)
        self.assertEqual(len(novas), 1)
        self.assertEqual(novas[0]["caixa"], (168, 128, 232, 152))
        pessoa, alertas = TestDetalheOculos().avaliar(pontos, novas)
        self.assertEqual(pessoa["epis"]["oculos"], "presente")
        self.assertEqual(resumo["pendentes"], 0)
        self.assertFalse(alertas)

    def test_indicio_auxiliar_fraco_nao_e_promovido_a_presenca(self):
        novas, _, pontos = self.avaliar(ModeloFake(), ModeloFake([((80, 40, 144, 64), 1, .42)]))
        pessoa, alertas = TestDetalheOculos().avaliar(pontos, novas)
        self.assertEqual(pessoa["epis"]["oculos"], "inconclusivo")
        self.assertIn("Evidência fraca", pessoa["epis_motivos"]["oculos"])
        self.assertFalse(alertas)

    def test_positivo_principal_evitar_segunda_inferencia_auxiliar(self):
        auxiliar = ModeloFake()
        self.avaliar(ModeloFake([((80, 40, 144, 64), 1, .8)]), auxiliar)
        self.assertFalse(auxiliar.chamadas)

    def test_positivo_global_evitar_ambos_recortes(self):
        principal, auxiliar = ModeloFake(), ModeloFake()
        self.avaliar(principal, auxiliar, [{"classe": "oculos", "caixa": (168, 128, 232, 152), "confianca": .8}])
        self.assertFalse(principal.chamadas)
        self.assertFalse(auxiliar.chamadas)

    def test_falha_auxiliar_nao_e_avaliacao_negativa_valida(self):
        novas, resumo, pontos = self.avaliar(ModeloFake(), ModeloFake(falha=True))
        self.assertEqual(resumo["erros"], ["RuntimeError"])
        self.assertEqual(resumo["pendentes"], 1)
        self.assertNotIn("oculos", pontos["_epi_local_avaliados"])
        pessoa, alertas = TestDetalheOculos().avaliar(pontos, novas)
        self.assertEqual(pessoa["epis"]["oculos"], "inconclusivo")
        self.assertFalse(alertas)

    def test_falha_auxiliar_nao_invalida_outro_epi_avaliado(self):
        _, _, pontos = self.avaliar(ModeloFake(), ModeloFake(falha=True), obrigatorios=["capacete", "oculos"])
        self.assertIn("capacete", pontos["_epi_local_avaliados"])
        self.assertNotIn("oculos", pontos["_epi_local_avaliados"])

    def test_auxiliar_independente_sem_modelo_principal(self):
        novas, resumo, pontos = self.avaliar(None, ModeloFake([((80, 40, 144, 64), 1, .8)]))
        pessoa, _ = TestDetalheOculos().avaliar(pontos, novas)
        self.assertEqual(pessoa["epis"]["oculos"], "presente")
        self.assertEqual(resumo["concluidas"], 1)

    def test_positivo_auxiliar_encerra_pendencia_do_item_apos_falha_principal_local(self):
        novas, resumo, pontos = self.avaliar(ModeloFake(falha=True), ModeloFake([((80, 40, 144, 64), 1, .8)]))
        pessoa, alertas = TestDetalheOculos().avaliar(pontos, novas)
        self.assertEqual(pessoa["epis"]["oculos"], "presente")
        self.assertIn("oculos", pontos["_epi_local_avaliados"])
        self.assertEqual(resumo["pendentes"], 0)
        self.assertEqual(resumo["erros"], ["RuntimeError"])
        self.assertFalse(alertas)

    def test_auxiliar_nao_roda_para_capacete_sozinho(self):
        auxiliar = ModeloFake(falha=True)
        self.avaliar(ModeloFake(), auxiliar, obrigatorios=["capacete"])
        self.assertFalse(auxiliar.chamadas)

    def test_sem_modelos_nao_gera_avaliacao_local(self):
        novas, resumo, _ = self.avaliar(None, None)
        self.assertFalse(novas)
        self.assertEqual(resumo, {"concluidas": 0, "pendentes": 0, "erros": []})


class TestFluxoAuxiliar(unittest.TestCase):
    def test_falhas_e_auxiliar_independente_no_fluxo_real(self):
        for modo in ("principal_indisponivel", "aux_falha_local", "aux_falha_global", "aux_falha_carga"):
            with self.subTest(modo=modo), tempfile.TemporaryDirectory() as pasta:
                monitor = Monitor(base=pasta, modelo_epi=Path(pasta) / "principal.pt",
                                  modelo_oculos=Path(pasta) / "auxiliar.pt")
                monitor.epi_obrigatorio = ["oculos"]
                monitor.status["executando"] = True
                relogio = [0.0]
                globais = []

                class Camera:
                    leituras = 0

                    def isOpened(self):
                        return True

                    def read(self):
                        self.leituras += 1
                        relogio[0] += 1.5
                        if self.leituras <= 3:
                            return True, np.zeros(TAMANHO, dtype=np.uint8)
                        monitor.stop.set()
                        return False, None

                    def release(self):
                        pass

                class Contexto:
                    def __enter__(self):
                        return self

                    def __exit__(self, *_):
                        pass

                    def process(self, _):
                        pontos = [SimpleNamespace(x=x, y=y) for x, y in ((.34, .1), (.66, .1), (.5, .16))]
                        face = SimpleNamespace(score=[.95], location_data=SimpleNamespace(
                            relative_keypoints=pontos,
                            relative_bounding_box=SimpleNamespace(xmin=.2, ymin=.02, width=.6, height=.3)))
                        return SimpleNamespace(pose_landmarks=None, detections=[face])

                class Auxiliar(ModeloFake):
                    def __call__(self, imagem, **opcoes):
                        if modo == "aux_falha_global":
                            raise RuntimeError("falha global simulada")
                        if imagem.shape == TAMANHO:
                            globais.append(opcoes)
                            return ModeloFake()(imagem)
                        if modo == "aux_falha_local":
                            raise RuntimeError("falha local simulada")
                        return super().__call__(imagem, **opcoes)

                auxiliar = Auxiliar([((80, 40, 144, 64), 1, .8)])

                def carregar(caminho):
                    nome = Path(caminho).name
                    if nome == "principal.pt":
                        if modo == "principal_indisponivel":
                            raise RuntimeError("falha de carga principal simulada")
                        return ModeloFake()
                    if nome == "auxiliar.pt":
                        if modo == "aux_falha_carga":
                            raise RuntimeError("falha de carga auxiliar simulada")
                        return auxiliar
                    return lambda *_a, **_k: [SimpleNamespace(boxes=SimpleNamespace(xyxy=np.array([CAIXA])))]

                mp = SimpleNamespace(solutions=SimpleNamespace(
                    pose=SimpleNamespace(Pose=lambda **_: Contexto()),
                    face_detection=SimpleNamespace(FaceDetection=lambda **_: Contexto())))
                with patch("main.abrir_camera", return_value=Camera()), patch("main.time", SimpleNamespace(
                    monotonic=lambda: relogio[0]
                )), patch.dict("sys.modules", {"mediapipe": mp, "ultralytics": SimpleNamespace(YOLO=carregar)}), patch.object(
                    monitor, "alerta"
                ) as alerta:
                    monitor.executar()
                self.assertEqual(monitor.status["estado"], "parado", monitor.status["mensagem"])
                esperado = "presente" if modo == "principal_indisponivel" else "inconclusivo"
                self.assertEqual(monitor.status["deteccoes"][0]["epis"]["oculos"], esperado)
                self.assertTrue(all(c["classes"] == [1] and c["imgsz"] == 640 for c in globais))
                alerta.assert_not_called()


class TestRotuloMonitoramento(unittest.TestCase):
    def test_inconclusivo_e_amarelo_nao_verde(self):
        linhas, cor = rotulo_monitoramento({"id": 1, "postura": "Em pe", "epis": {"oculos": "inconclusivo"}})
        self.assertEqual(cor, (0, 180, 255))
        self.assertIn("EPI inconclusivo: oculos", linhas)

    def test_ausencia_real_nao_oculta_outro_item_inconclusivo(self):
        linhas, cor = rotulo_monitoramento({"id": 1, "postura": "Em pe", "epi_faltando": ["capacete"],
                                            "epis": {"capacete": "possivel_ausencia", "oculos": "inconclusivo"}})
        self.assertEqual(cor, (50, 70, 230))
        self.assertEqual(linhas[1:], ["Possivel ausencia: capacete", "EPI inconclusivo: oculos"])

    def test_presenca_confirmada_verde_sem_motivo_inconclusivo(self):
        linhas, cor = rotulo_monitoramento({"id": 1, "postura": "Em pe", "epis": {"oculos": "presente"}})
        self.assertEqual(cor, (70, 190, 100))
        self.assertEqual(linhas, ["Pessoa 1 | Em pe"])


if __name__ == "__main__":
    unittest.main()
