"""Executa os testes sem câmera física nem SMTP real; gera relatório local."""

import io
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

BASE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(BASE), str(BASE / 'tests')]
os.environ.update(VIGIAAI_TESTE='0', NOTIFICACOES_ATIVAS='1', SALVAR_IMAGEM_OCORRENCIA='1',
                  VIGIAAI_DEVICE='cpu', VIGIAAI_MEDIA_DIR=str(BASE / 'diagnosticos/midia-testes'))
import cv2

original = cv2.VideoCapture


def video_local(fonte, *args, **kwargs):
    if not isinstance(fonte, str) or not Path(fonte).is_file():
        raise AssertionError('Webcam física/URL bloqueada na validação automatizada.')
    return original(fonte, *args, **kwargs)


saida = io.StringIO()
with patch('smtplib.SMTP_SSL', side_effect=AssertionError('SMTP real bloqueado.')), patch(
    'cv2.VideoCapture', side_effect=video_local
):
    suite = unittest.defaultTestLoader.discover(str(BASE / 'tests'), pattern='test_*.py')
    resultado = unittest.TextTestRunner(stream=saida, verbosity=2).run(suite)
destino = BASE / 'diagnosticos/integracao-20261031'
destino.mkdir(parents=True, exist_ok=True)
(destino / 'testes-python.log').write_text(saida.getvalue(), encoding='utf-8')
resumo = dict(testes=resultado.testsRun, falhas=len(resultado.failures), erros=len(resultado.errors),
              ignorados=len(resultado.skipped), camera_fisica=False, smtp_real=False,
              detalhes=[dict(teste=str(t), traceback=erro) for t, erro in resultado.failures + resultado.errors])
(destino / 'testes-python.json').write_text(json.dumps(resumo, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(resumo, ensure_ascii=False), flush=True)
raise SystemExit(not resultado.wasSuccessful())
