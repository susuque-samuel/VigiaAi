"""Reproduz o fluxo real nas capturas fornecidas, sem câmera ou SMTP."""

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from main import BASE, Monitor
from diagnosticar_oculos import IMAGENS


def main():
    registros = []
    with tempfile.TemporaryDirectory(prefix="vigia-oculos-") as pasta:
        for nome, com_oculos in IMAGENS:
            arquivo = Path.home() / "AppData/Local/Temp" / f"codex-clipboard-{nome}.png"
            imagem = cv2.imread(str(arquivo))
            if imagem is None:
                raise FileNotFoundError(arquivo)
            imagem = cv2.flip(imagem[105:414, 333:923], 1)
            monitor = Monitor(base=pasta)
            monitor.epi_obrigatorio = ["oculos"]
            monitor.status.update(executando=True, estado="iniciando")
            # O teste de tempo real já cobre os 3 segundos; aqui são 3 observações.
            monitor.motor.confirmacao_epi = 0.001

            class Camera:
                leituras = 0

                def isOpened(self):
                    return True

                def read(self):
                    self.leituras += 1
                    if self.leituras <= 3:
                        return True, imagem.copy()
                    monitor.stop.set()
                    return False, None

                def release(self):
                    pass

            with patch("main.abrir_camera", return_value=Camera()), patch.object(monitor, "alerta") as alerta:
                monitor.executar()
            status = monitor.snapshot()
            registro = {
                "imagem": nome, "com_oculos": com_oculos, "erro": status["mensagem"],
                "pessoas": status["deteccoes"], "alertas": alerta.call_count,
                "erro_auxiliar": status["oculos_erro"],
            }
            registros.append(registro)
            print(json.dumps(registro, ensure_ascii=False), flush=True)
        caminho = BASE / "diagnosticos/oculos_20261019/fluxo_corrigido.json"
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(json.dumps(registros, ensure_ascii=False, indent=2), encoding="utf-8")
    positivos = [r for r in registros if r["com_oculos"]]
    assert all(r["pessoas"] and r["pessoas"][0]["epis"]["oculos"] != "possivel_ausencia" for r in positivos), "Ainda há falso alerta nas imagens com óculos."
    assert sum(r["pessoas"][0]["epis"]["oculos"] == "presente" for r in positivos) >= 3
    negativo = next(r for r in registros if not r["com_oculos"])
    assert negativo["pessoas"] and negativo["pessoas"][0]["epis"]["oculos"] == "possivel_ausencia"
    print("OK: três presenças, perfil inconclusivo e ausência na imagem sem óculos.", flush=True)


if __name__ == "__main__":
    main()
