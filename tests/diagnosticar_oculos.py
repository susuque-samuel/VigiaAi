"""Diagnóstico offline das capturas de tela; não treina nem modifica modelos."""

import json
from pathlib import Path
import sys

import cv2
import mediapipe as mp
import torch
from ultralytics import YOLO

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
from main import MODELO_EPI

IMAGENS = [
    ("2d66a8e7-ba89-4484-a2e4-5a8efcdd27ad", True),
    ("1d741a26-4b68-494c-8aeb-6ee2e8044636", True),
    ("92cb2cef-e717-43d3-a0b8-de43a384ba98", True),
    ("20e90d7b-cce2-4bbe-a4db-11abdf5f751c", False),
    ("cab0fe87-49d5-4c5c-bde3-3a20222ca307", True),
]


def main():
    torch.set_num_threads(4)
    pasta = BASE / "diagnosticos" / "oculos_20261019"
    pasta.mkdir(parents=True, exist_ok=True)
    imagens = []
    with mp.solutions.face_detection.FaceDetection(
        model_selection=0, min_detection_confidence=0.5
    ) as detector:
        for nome, com_oculos in IMAGENS:
            arquivo = Path.home() / "AppData/Local/Temp" / f"codex-clipboard-{nome}.png"
            quadro = cv2.imread(str(arquivo))
            if quadro is None:
                raise FileNotFoundError(arquivo)
            quadro = quadro[105:414, 333:923]
            resultado = detector.process(cv2.cvtColor(quadro, cv2.COLOR_BGR2RGB))
            altura, largura = quadro.shape[:2]
            faces = []
            for deteccao in resultado.detections or []:
                box = deteccao.location_data.relative_bounding_box
                x1, y1 = max(0, int(box.xmin * largura)), max(0, int(box.ymin * altura))
                x2, y2 = min(largura, int((box.xmin + box.width) * largura)), min(altura, int((box.ymin + box.height) * altura))
                pontos = deteccao.location_data.relative_keypoints
                olhos_y = (pontos[0].y + pontos[1].y) / 2 * altura
                faces.append((x1, y1, x2, y2, olhos_y))
            face = max(faces, key=lambda b: (b[2] - b[0]) * (b[3] - b[1])) if faces else None
            imagens.append((nome, com_oculos, quadro, face))
    modelos = [
        MODELO_EPI,
        BASE / "runs/detect/treinamento_epi-2/weights/best.pt",
        BASE / "runs/detect/treinamento_epi_20261007_143226/ajuste/weights/best.pt",
    ]
    saida = []
    for caminho in dict.fromkeys(modelos):
        modelo = YOLO(str(caminho))
        for nome, com_oculos, quadro, face in imagens:
            regioes = [("quadro", quadro)]
            if face:
                x1, y1, x2, y2, olhos_y = face
                # Recorte superior do rosto: contexto ao redor das sobrancelhas/olhos.
                margem = int((x2 - x1) * 0.15)
                tx1, tx2 = max(0, x1 - margem), min(quadro.shape[1], x2 + margem)
                ty1 = max(0, int(olhos_y - (x2 - x1) * 0.45))
                ty2 = min(quadro.shape[0], int(olhos_y + (x2 - x1) * 0.45))
                regioes.append(("olhos", quadro[ty1:ty2, tx1:tx2]))
            registro = {"modelo": str(caminho.relative_to(BASE)), "imagem": nome,
                        "com_oculos": com_oculos, "rosto": face, "previsoes": {}}
            for tipo, imagem in regioes:
                resultado = modelo(imagem, conf=0.05, verbose=False)[0]
                registro["previsoes"][tipo] = [
                    {"classe": resultado.names[int(classe)], "confianca": round(float(conf), 4),
                     "caixa": [round(float(v), 2) for v in box]}
                    for box, classe, conf in zip(resultado.boxes.xyxy, resultado.boxes.cls, resultado.boxes.conf)
                ]
            saida.append(registro)
            print(json.dumps(registro, ensure_ascii=False), flush=True)
    (pasta / "modelos.json").write_text(json.dumps(saida, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
