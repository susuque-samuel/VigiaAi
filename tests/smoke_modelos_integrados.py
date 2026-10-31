"""Inferência local em uma amostra preservada; não mede precisão nem treina."""

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
config = BASE / 'diagnosticos/integracao-20261031/ultralytics'
config.mkdir(parents=True, exist_ok=True)
os.environ.update(YOLO_CONFIG_DIR=str(config), YOLO_AUTOINSTALL='false', VIGIAAI_DEVICE='cpu', VIGIAAI_TESTE='1')

import cv2
import torch
from main import Monitor

torch.set_num_threads(4)
amostra = next(iter(sorted((BASE / 'amostras_epi/pendentes').glob('*.jpg'))), None)
if amostra is None:
    raise FileNotFoundError('Sem amostra para a verificação local; nenhum dado será fabricado.')
hash_antes = hashlib.sha256(amostra.read_bytes()).hexdigest()
imagem = cv2.imread(str(amostra))
if imagem is None:
    raise ValueError('Amostra ilegível.')
with tempfile.TemporaryDirectory(prefix='vigiaai-smoke-') as pasta:
    monitor = Monitor(base=pasta)
    monitor.epi_obrigatorio = ['capacete', 'oculos']
    monitor.status.update(executando=True, estado='iniciando')

    class Camera:
        leituras = 0

        def isOpened(self): return True

        def read(self):
            self.leituras += 1
            if self.leituras <= 3:
                return True, cv2.flip(imagem, 1)
            monitor.stop.set()
            return False, None

        def release(self): pass

    with patch('main.abrir_camera', return_value=Camera()), patch.object(monitor, 'alerta') as alertas:
        monitor.executar()
    s = monitor.snapshot()
    assert s['estado'] == 'parado', s['mensagem']
    assert monitor.frame is not None, 'Nenhum quadro processado.'
    assert s['epi_erro'] is None and s['oculos_erro'] is None, 'Falha de detector.'
    assert hashlib.sha256(amostra.read_bytes()).hexdigest() == hash_antes, 'A amostra mudou.'
    resumo = dict(resultado='ok', quadros=3, pessoas=len(s['deteccoes']),
                  epis=[p['epis'] for p in s['deteccoes']], reanalises=s['epi_reanalises'],
                  erro_reanalise=s['epi_reanalise_erro'], alertas_simulados=alertas.call_count,
                  camera_fisica=False, smtp_real=False, amostra_modificada=False,
                  limitacao='Uma amostra usada só como smoke test; não é avaliação de acurácia, distância ou tempo real.')
    (BASE / 'diagnosticos/integracao-20261031/smoke-modelos.json').write_text(json.dumps(resumo, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(resumo, ensure_ascii=False), flush=True)
