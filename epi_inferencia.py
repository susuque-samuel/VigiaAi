"""Segunda análise de EPIs em recortes, sem dependências extras ou pesos novos."""

import math

from epi_monitoramento import associar_epis, identificar_epi


def extrair_deteccoes_epi(resultados, piso_oculos=0.5, origem=(0, 0), itens=None, piso_outros=0.5):
    deteccoes = []
    for resultado in resultados:
        for box, classe, conf in zip(resultado.boxes.xyxy, resultado.boxes.cls, resultado.boxes.conf):
            nome = resultado.names[int(classe)]
            item = identificar_epi(nome)
            minimo = piso_oculos if item == "oculos" else piso_outros
            confianca = float(conf)
            if item is None or (itens is not None and item not in itens):
                continue
            if not math.isfinite(confianca) or confianca < minimo:
                continue
            x1, y1, x2, y2 = box.tolist()
            if not all(math.isfinite(v) for v in (x1, y1, x2, y2)) or x2 <= x1 or y2 <= y1:
                continue
            deteccoes.append({
                "caixa": (x1 + origem[0], y1 + origem[1], x2 + origem[0], y2 + origem[1]),
                "classe": nome, "confianca": confianca,
            })
    return deteccoes


def regiao_epi(caixa, tamanho):
    x1, y1, x2, y2 = map(int, caixa)
    margem = max(8, min(32, round(max(x2 - x1, y2 - y1) * 0.03)))
    return (max(0, x1 - margem), max(0, y1 - margem),
            min(tamanho[1], x2 + margem), min(tamanho[0], y2 + margem))


def reanalisar_epi_por_pessoa(modelo, quadro, caixas, pontos, obrigatorios, deteccoes,
                             piso_oculos=0.15, limite=4, rodada=0, modelo_oculos=None):
    """Mantém o limiar de 0,5; pendências/falhas não são evidência de ausência."""
    pessoas = [{"id": i, "caixa": tuple(caixa), "pontos": landmarks}
               for i, (caixa, landmarks) in enumerate(zip(caixas, pontos))]
    presentes, _ = associar_epis(pessoas, deteccoes)
    modelos = []
    for detector, permitidos in ((modelo, set(obrigatorios)), (modelo_oculos, {"oculos"} & set(obrigatorios))):
        if detector is None or not permitidos:
            continue
        nomes = detector.names
        classes = dict(enumerate(nomes)) if isinstance(nomes, list) else nomes
        itens_modelo = {identificar_epi(nome) for nome in classes.values()} & permitidos
        if itens_modelo:
            modelos.append((detector, classes, itens_modelo))
    suportados = set().union(*(itens for _, _, itens in modelos))
    candidatos = []
    for pessoa, landmarks in zip(pessoas, pontos):
        itens = (set(obrigatorios) & suportados) - presentes[pessoa["id"]]
        landmarks["_epi_local_necessarios"] = tuple(sorted(itens))
        landmarks["_epi_local_avaliados"] = ()
        if itens:
            candidatos.append((pessoa, landmarks, itens))
    if candidatos:
        inicio = rodada % len(candidatos)
        candidatos = candidatos[inicio:] + candidatos[:inicio]
    novas = []
    concluidas = 0
    erros = set()
    for pessoa, landmarks, itens in candidatos[:max(0, limite)]:
        x1, y1, x2, y2 = regiao_epi(pessoa["caixa"], quadro.shape)
        if x2 <= x1 or y2 <= y1:
            continue
        avaliados, falharam = set(), set()
        for detector, classes, itens_modelo in modelos:
            positivos, _ = associar_epis(pessoas, deteccoes + novas)
            avaliados.update(itens & positivos[pessoa["id"]])
            solicitados = (itens & itens_modelo) - positivos[pessoa["id"]]
            if not solicitados:
                continue
            try:
                indices = [i for i, nome in classes.items() if identificar_epi(nome) in solicitados]
                piso = piso_oculos if "oculos" in solicitados else 0.25
                saida = detector(quadro[y1:y2, x1:x2], classes=indices, conf=piso, imgsz=640, verbose=False)
                locais = extrair_deteccoes_epi(saida, piso_oculos=piso_oculos, origem=(x1, y1),
                                              itens=solicitados, piso_outros=0.25)
                # Descarta previsões em vizinhos capturados pela margem do recorte.
                px1, py1, px2, py2 = pessoa["caixa"]
                for deteccao in locais:
                    ex1, ey1, ex2, ey2 = deteccao["caixa"]
                    cx, cy = (ex1 + ex2) / 2, (ey1 + ey2) / 2
                    if px1 <= cx <= px2 and py1 - (py2 - py1) * 0.1 <= cy <= py2:
                        deteccao["local"] = True
                        novas.append(deteccao)
                avaliados.update(solicitados)
            except Exception as erro:
                erros.add(type(erro).__name__)
                falharam.update(solicitados)
        positivos, _ = associar_epis(pessoas, deteccoes + novas)
        avaliados = (avaliados - falharam) | (itens & positivos[pessoa["id"]])
        landmarks["_epi_local_avaliados"] = tuple(sorted(avaliados))
        if itens <= avaliados:
            concluidas += 1
    return novas, {"concluidas": concluidas, "pendentes": len(candidatos) - concluidas,
                   "erros": sorted(erros)}
