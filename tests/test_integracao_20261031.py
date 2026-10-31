"""Regressões da integração: política, fontes, notificações e métricas."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np

from avaliar_eventos import avaliar
from epi_monitoramento import MotorAlertas, avaliar_postura
from main import Monitor, criar_app
from test_epi_distancia import CAIXA, TAMANHO, pontos_visiveis

SMTP = dict(SMTP_HOST='smtp.example.test', SMTP_PORTA='465', SMTP_SENHA='somente-fixture',
            EMAIL_REMETENTE='origem@example.test', EMAIL_DESTINATARIO='destino@example.test',
            VIGIAAI_TESTE='0', NOTIFICACOES_ATIVAS='1')


class TestPoliticaIntegrada(unittest.TestCase):
    def estado(self, modo, deteccoes=()):
        motor = MotorAlertas(modo_ausencia=modo)
        for t in (0, 1.5, 3):
            pessoas, alertas = motor.avaliar([CAIXA], [pontos_visiveis()], list(deteccoes),
                                            ['capacete'], {'capacete'}, TAMANHO, t)
        return pessoas[0], alertas

    def test_observacao_preserva_possivel_aviso_sem_promover_a_certeza(self):
        pessoa, alertas = self.estado('observacao')
        self.assertEqual(pessoa['epis']['capacete'], 'possivel_ausencia')
        self.assertEqual(alertas[0]['confirmacao'], 'verificacao_humana_pendente')

    def test_modo_explicito_sem_classe_negativa_fica_inconclusivo(self):
        pessoa, alertas = self.estado('explicita')
        self.assertEqual(pessoa['epis']['capacete'], 'inconclusivo')
        self.assertIn('evidência explícita', pessoa['epis_motivos']['capacete'])
        self.assertFalse(alertas)

    def test_classe_negativa_forte_ainda_funciona_em_modo_explicito(self):
        pessoa, alertas = self.estado('explicita', [dict(classe='no_helmet', caixa=(150, 105, 250, 155), confianca=.9)])
        self.assertEqual(pessoa['epis']['capacete'], 'possivel_ausencia')
        self.assertEqual(len(alertas), 1)

    def test_conflito_positivo_negativo_nao_gera_aviso(self):
        caixas = [dict(classe=c, caixa=(150, 105, 250, 155), confianca=.9) for c in ('capacete', 'no_helmet')]
        pessoa, alertas = self.estado('observacao', caixas)
        self.assertEqual(pessoa['epis']['capacete'], 'inconclusivo')
        self.assertIn('conflito', pessoa['epis_motivos']['capacete'])
        self.assertFalse(alertas)

    def test_modo_salvo_preserva_extras_e_limpa_confirmacao_epi(self):
        with tempfile.TemporaryDirectory() as pasta:
            config = Path(pasta) / 'config_epi.json'
            config.write_text(json.dumps(dict(obrigatorios=['capacete'], identificador_local='preservar')), encoding='utf-8')
            monitor = Monitor(base=pasta, modelo_epi=None, modelo_oculos=None)
            self.assertEqual(monitor.modo_ausencia, 'observacao')
            chave = (1, 'epi', 'capacete')
            monitor.motor.confirmador.observar(chave, True, 0, 3)
            monitor.motor.confirmador.marcar_alerta([chave], 0)
            monitor.configurar_epi(['oculos'], 4, 'explicita')
            self.assertFalse(monitor.motor.confirmador.avisados_continuos)
            restaurado = Monitor(base=pasta, modelo_epi=None, modelo_oculos=None)
            self.assertEqual(restaurado.motor.modo_ausencia, 'explicita')
            self.assertEqual(restaurado.epi_obrigatorio, ['oculos'])
            self.assertEqual(json.loads(config.read_text())['identificador_local'], 'preservar')

    def test_api_valida_modos_e_nao_altera_em_erro(self):
        with tempfile.TemporaryDirectory() as pasta:
            monitor = Monitor(base=pasta, modelo_epi=None, modelo_oculos=None)
            cliente = criar_app(monitor).test_client()
            for invalido in ([], {}, True, 'qualquer'):
                r = cliente.post('/configurar-epi', json=dict(obrigatorios=['capacete'], modo_ausencia=invalido))
                self.assertEqual(r.status_code, 400)
                self.assertEqual(monitor.modo_ausencia, 'observacao')
            r = cliente.post('/configurar-epi', json=dict(obrigatorios=['capacete'], modo_ausencia='explicita'))
            self.assertEqual(r.status_code, 200)
            self.assertEqual(cliente.get('/status').json['modo_ausencia'], 'explicita')

    def test_busca_de_video_preserva_modo_escolhido_e_limpa_historico(self):
        with tempfile.TemporaryDirectory() as pasta:
            monitor = Monitor(base=pasta, modelo_epi=None, modelo_oculos=None)
            central = criar_app(monitor).extensions['central']
            monitor.configurar_epi(['capacete'], 3, 'observacao')
            central.busca, central.pausado, central.passo = .5, True, True
            cap = Mock()
            cap.set.return_value = True
            self.assertEqual(central.antes_quadro(cap, 0, 20), 10)
            self.assertEqual(monitor.motor.modo_ausencia, 'observacao')
            self.assertFalse(monitor.motor.temporais)


class TestNotificacoesIntegradas(unittest.TestCase):
    def test_central_camera_normal_video_simulado(self):
        with tempfile.TemporaryDirectory() as pasta:
            monitor = Monitor(base=pasta, modelo_epi=None, modelo_oculos=None)
            central = criar_app(monitor).extensions['central']
            with patch.object(monitor, 'iniciar') as iniciar:
                central.fonte = dict(modo='camera', id='camera-0', nome='Câmera', indice=0)
                central.iniciar()
                iniciar.assert_called_with(demonstracao=False)
                central.fonte = dict(modo='video', id='teste', nome='Vídeo')
                central.iniciar()
                iniciar.assert_called_with(demonstracao=True)

    def test_email_camera_passa_pelo_smtp_simulado(self):
        with tempfile.TemporaryDirectory() as pasta, patch.dict(os.environ, SMTP), patch('main.smtplib.SMTP_SSL') as smtp:
            monitor = Monitor(base=pasta, modelo_epi=None, modelo_oculos=None)
            evento = dict(motivo='Somente teste', data='31/10/2026')
            monitor.email(evento, None)
            smtp.return_value.__enter__.return_value.send_message.assert_called_once()
            self.assertEqual(evento['email'], 'enviado')
            self.assertEqual(smtp.call_args.kwargs['timeout'], 15)

    def test_video_nao_envia_mesmo_sem_flag_demonstracao(self):
        with tempfile.TemporaryDirectory() as pasta, patch.dict(os.environ, SMTP), patch('main.smtplib.SMTP_SSL') as smtp:
            monitor = Monitor(base=pasta, modelo_epi=None, modelo_oculos=None, fonte_video='video-fixture.avi')
            evento = dict(motivo='Somente teste', data='31/10/2026')
            monitor.email(evento, None)
            smtp.assert_not_called()

    def test_video_nao_salva_foto_e_marca_evento_como_simulado(self):
        with tempfile.TemporaryDirectory() as pasta, patch.dict(os.environ, SMTP), patch('main.salvar_jpeg') as foto, patch('main.smtplib.SMTP_SSL') as smtp:
            monitor = Monitor(base=pasta, modelo_epi=None, modelo_oculos=None, fonte_video='video-fixture.avi')
            monitor.alerta(np.zeros((80, 120, 3), np.uint8), dict(tipo='queda', pessoa_id=1,
                           motivo='Somente teste', chaves=[(1, 'queda', '')]), 0)
            foto.assert_not_called()
            smtp.assert_not_called()
            self.assertTrue(monitor.eventos[0]['simulacao'])

    def test_evento_simulado_nao_envia_apos_troca_de_fonte(self):
        with tempfile.TemporaryDirectory() as pasta, patch.dict(os.environ, SMTP), patch('main.smtplib.SMTP_SSL') as smtp:
            monitor = Monitor(base=pasta, modelo_epi=None, modelo_oculos=None)
            monitor.email(dict(motivo='Somente teste', data='31/10/2026', simulacao=True), None)
            smtp.assert_not_called()

    def test_modo_teste_e_chave_desativada_bloqueiam_smtp(self):
        for flag in ({'VIGIAAI_TESTE': '1'}, {'NOTIFICACOES_ATIVAS': '0'}):
            with tempfile.TemporaryDirectory() as pasta, patch.dict(os.environ, SMTP | flag), patch('main.smtplib.SMTP_SSL') as smtp:
                monitor = Monitor(base=pasta, modelo_epi=None, modelo_oculos=None)
                monitor.email(dict(motivo='Somente teste', data='31/10/2026'), None)
                smtp.assert_not_called()

    def test_status_notificacoes_respeita_fonte_e_modo_teste(self):
        with tempfile.TemporaryDirectory() as pasta, patch.dict(os.environ, SMTP):
            monitor = Monitor(base=pasta, modelo_epi=None, modelo_oculos=None)
            central = criar_app(monitor).extensions['central']
            monitor.thread = SimpleNamespace(is_alive=lambda: True)
            central.fonte = dict(modo='camera', id='camera-0', nome='Câmera', indice=0)
            self.assertTrue(central.snapshot()['notificacoes_reais'])
            with patch.dict(os.environ, {'VIGIAAI_TESTE': '1'}):
                self.assertFalse(central.snapshot()['notificacoes_reais'])
            central.fonte = dict(modo='video', id='video', nome='Vídeo')
            self.assertFalse(central.snapshot()['notificacoes_reais'])


class TestMetricasIntegradas(unittest.TestCase):
    def test_filtro_epi_nao_reinterpreta_referencia_antiga(self):
        ref = dict(video_id='fixture', duracao_segundos=10, eventos=[dict(inicio=2, fim=4, pessoa_id=1)])
        pred = dict(video_id='fixture', duracao_segundos=10, eventos=[dict(tempo=3, pessoa_id=1, tipo='epi')])
        r = avaliar(ref, pred, tipo='epi')
        self.assertEqual(r['eventos_reais'], 0)
        self.assertEqual(r['detectados'], 0)
        self.assertEqual(r['falsos_alertas'], 1)

    def test_epi_nao_conta_como_queda_nem_em_referencia_antiga(self):
        ref = dict(video_id='fixture', duracao_segundos=10, eventos=[dict(inicio=2, fim=4, pessoa_id=1)])
        pred = dict(video_id='fixture', duracao_segundos=10, eventos=[dict(tempo=3, pessoa_id=1, tipo='epi')])
        r = avaliar(ref, pred)
        self.assertEqual(r['detectados'], 0)
        self.assertEqual(r['por_tipo']['queda']['perdidos'], 1)
        self.assertEqual(r['por_tipo']['epi']['falsos_alertas'], 1)

    def test_separa_tipos_e_filtro_epi_nao_contabiliza_quedas(self):
        ref = dict(video_id='fixture', duracao_segundos=10, eventos=[dict(inicio=2, fim=4, pessoa_id=1, tipo=t) for t in ('queda','epi')])
        pred = dict(video_id='fixture', duracao_segundos=10, eventos=[dict(tempo=3, pessoa_id=1, tipo=t) for t in ('queda','epi')])
        r = avaliar(ref, pred)
        self.assertEqual(r['detectados'], 2)
        self.assertEqual(r['por_tipo']['queda']['detectados'], 1)
        self.assertEqual(avaliar(ref, pred, tipo='epi')['eventos_reais'], 1)

    def test_epi_diferente_nao_e_acerto_quando_item_foi_anotado(self):
        ref = dict(video_id='fixture', duracao_segundos=10, eventos=[dict(inicio=2, fim=4, pessoa_id=1, tipo='epi', epis=['capacete'])])
        pred = dict(video_id='fixture', duracao_segundos=10, eventos=[dict(tempo=3, pessoa_id=1, tipo='epi', epis=['oculos'])])
        self.assertEqual(avaliar(ref, pred)['detectados'], 0)


class TestCadenciaIntegrada(unittest.TestCase):
    @staticmethod
    def ler(motor, t, deitada=True, pontos=None):
        pontos = dict(pontos_visiveis()) if pontos is None else pontos
        if deitada and pontos:
            pontos.update({11: (.2,.4,1), 12: (.3,.4,1), 23: (.7,.45,1), 24: (.8,.45,1)})
        return motor.avaliar([CAIXA], [pontos], [], [], set(), TAMANHO, t, processamento_segundos=3)

    def test_baixa_cadencia_nao_inventa_movimento_e_avisa_uma_vez(self):
        motor = MotorAlertas(intervalo=0)
        avisos = []
        for t in (0, 3, 6, 9, 12):
            pessoas, alertas = self.ler(motor, t)
            avisos.extend(alertas)
        self.assertEqual(len(avisos), 1)
        self.assertEqual(avisos[0]['classificacao'], 'deitada_persistente_baixa_cadencia')
        self.assertEqual(pessoas[0]['imobilidade_segundos'], 0)
        self.assertIsNone(pessoas[0]['velocidade_corpo'])

    def test_pose_perdida_interrompe_persistencia(self):
        motor = MotorAlertas()
        self.ler(motor, 0)
        self.ler(motor, 3)
        self.ler(motor, 4, pontos={})
        for t in (6, 9):
            pessoas, alertas = self.ler(motor, t)
            self.assertFalse(alertas)
        self.assertEqual(pessoas[0]['queda_quadros'], 2)

    def test_recuperacao_em_baixa_cadencia_permite_novo_episodio(self):
        motor = MotorAlertas(intervalo=0)
        for t in (0,3,6):
            self.ler(motor, t)
        for t in (9,12,15):
            self.ler(motor, t, deitada=False)
        self.assertFalse(motor.temporais[1].emitiu)
        avisos = []
        for t in (18,21,24):
            _, alertas = self.ler(motor, t)
            avisos.extend(alertas)
        self.assertEqual(len(avisos), 1)

    def test_pausa_longa_nao_usa_persistencia_anterior(self):
        motor = MotorAlertas()
        self.ler(motor, 0)
        self.ler(motor, 3)
        pessoas, alertas = self.ler(motor, 30)
        self.assertFalse(alertas)
        self.assertEqual(pessoas[0]['queda_quadros'], 1)


if __name__ == '__main__':
    unittest.main()
