"""Avalia alertas contra eventos independentes anotados; sem câmera ou SMTP."""

import argparse
import json
import math
from pathlib import Path
from statistics import mean


def avaliar(referencia, previsoes, tolerancia=3, tipo=None):
    duracao = referencia['duracao_segundos']
    if not math.isfinite(duracao) or duracao <= 0 or not math.isfinite(tolerancia) or tolerancia < 0:
        raise ValueError('Duração precisa ser positiva e tolerância não negativa.')
    eventos, alertas = referencia['eventos'], previsoes['eventos']
    if referencia['video_id'] != previsoes['video_id']:
        raise ValueError('Referência e previsões devem pertencer ao mesmo vídeo.')
    if abs(duracao - previsoes['duracao_segundos']) > max(.1, duracao * .01):
        raise ValueError('Durações incompatíveis: não compare recortes diferentes.')
    if tipo not in (None, 'queda', 'epi'):
        raise ValueError('Tipo deve ser queda ou epi.')

    def tipo_de(evento):
        # Referências antigas eram de quedas. Nunca infere "queda" a partir
        # de um alerta explicitamente classificado como EPI.
        valor = evento.get('tipo', 'queda')
        if valor not in ('queda', 'epi'):
            raise ValueError('Tipo de evento inválido.')
        return valor
    for e in eventos:
        tipo_de(e)
        if not (0 <= e['inicio'] <= e['fim'] <= duracao and 'pessoa_id' in e):
            raise ValueError('Evento de referência inválido.')
    for a in alertas:
        tipo_de(a)
        if not (math.isfinite(a['tempo']) and 0 <= a['tempo'] <= duracao and 'pessoa_id' in a):
            raise ValueError('Alerta inválido.')
    if tipo is not None:
        eventos = [e for e in eventos if tipo_de(e) == tipo]
        alertas = [a for a in alertas if tipo_de(a) == tipo]
    usados, latencias = set(), []
    falsos = []
    for a in sorted(alertas, key=lambda a: a['tempo']):
        candidatos = [i for i, e in enumerate(eventos) if i not in usados
                      and e['pessoa_id'] == a['pessoa_id']
                      and tipo_de(e) == tipo_de(a)
                      and (tipo_de(e) != 'epi' or 'epis' not in e or set(e['epis']) == set(a.get('epis', [])))
                      and e['inicio'] <= a['tempo'] <= min(duracao, e['fim'] + tolerancia)]
        if candidatos:
            i = min(candidatos, key=lambda i: eventos[i]['inicio'])
            usados.add(i)
            latencias.append(a['tempo'] - eventos[i]['inicio'])
        else:
            falsos.append(a)
    por_tipo = {}
    for categoria in ('queda', 'epi'):
        reais = [i for i, e in enumerate(eventos) if tipo_de(e) == categoria]
        acertos = sum(i in usados for i in reais)
        falsos_tipo = sum(tipo_de(a) == categoria for a in falsos)
        por_tipo[categoria] = dict(eventos_reais=len(reais), detectados=acertos, perdidos=len(reais)-acertos,
                                  recall_por_evento=acertos/len(reais) if reais else None,
                                  falsos_alertas=falsos_tipo, falsos_alertas_por_hora=falsos_tipo*3600/duracao)
    return dict(eventos_reais=len(eventos), detectados=len(usados), perdidos=len(eventos) - len(usados),
                recall_por_evento=len(usados) / len(eventos) if eventos else None,
                falsos_alertas=len(falsos), falsos_alertas_por_hora=len(falsos) * 3600 / duracao,
                latencias_segundos=latencias, tempo_medio_ate_alerta=mean(latencias) if latencias else None,
                eventos_perdidos=[e for i, e in enumerate(eventos) if i not in usados],
                por_tipo=por_tipo, tipo_filtrado=tipo,
                criterio='Associação um para um por tipo, pessoa, janela temporal e EPIs quando anotados; classificação clínica não avaliada.')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('referencia')
    p.add_argument('previsoes')
    p.add_argument('--tolerancia', type=float, default=3)
    p.add_argument('--tipo', choices=['queda', 'epi'], help='Avaliar somente o tipo indicado; referências antigas sem tipo usam queda por padrão.')
    p.add_argument('--saida', required=True)
    a = p.parse_args()
    resultado = avaliar(*[json.loads(Path(f).read_text(encoding='utf-8')) for f in (a.referencia, a.previsoes)], a.tolerancia, a.tipo)
    Path(a.saida).write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding='utf-8')
