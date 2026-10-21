# Confirmação por pessoa e coleta de imagens

Implementação de 19/10/2026.

## Usar o painel

Reinicie o servidor:

    .\.venv\Scripts\python.exe main.py

Abra http://127.0.0.1:5000 e clique em Iniciar monitoramento.
Os campos de câmera e SMTP continuam sendo lidos do .env.

Selecione os EPIs obrigatórios, ajuste o tempo de confirmação e clique em
Salvar política. A política permanece em config_epi.json. Se você alterar
o tempo pelo painel, esse valor salvo tem prioridade sobre o valor inicial
EPI_CONFIRMACAO_SEGUNDOS do .env.

## Estados da verificação de EPI

- Detectado: o modelo encontrou um item associado à região da pessoa.
- Verificando ausência: o item ainda não foi detectado, e há imagem
  suficiente da região do corpo para continuar observando.
- Possível ausência: a condição persistiu por pelo menos 3 quadros e pelo
  tempo configurado, por padrão 3 segundos. Pode gerar ocorrência.
- Inconclusivo: modelo indisponível, classe sem suporte, região oculta,
  pessoa pequena/cortada ou associação ambígua. Não gera alerta de EPI.

As regras geométricas e a visibilidade da pose são filtros conservadores.
Não comprovam que uma região esteja livre de toda oclusão. Os IDs são
temporários, baseados na sobreposição das caixas; podem mudar em movimentos
rápidos, cruzamentos e oclusões. Não representam a identidade do funcionário.
Uma perda de detecção interrompe a confirmação. Por padrão, intervalos maiores
que 2 segundos entre observações reiniciam a contagem. Desde o ajuste de
20/10/2026, a duração medida do processamento pode ampliar essa tolerância,
com limite de 10 segundos; pausas arbitrárias e pessoas ausentes continuam
reiniciando a confirmação. Três observações continuam sendo obrigatórias.

Os alertas têm intervalo independente por pessoa, tipo e EPI. Uma nova
pessoa não fica bloqueada pelo alerta de outra. A postura deitada tem
confirmação própria de 2 segundos e 3 quadros; continua sendo um alerta
de possível queda, sem análise completa do movimento de queda.

Valores iniciais opcionais no .env:

    EPI_CONFIRMACAO_SEGUNDOS=3
    QUEDA_CONFIRMACAO_SEGUNDOS=2
    COOLDOWN_SEGUNDOS=60

## Coletar imagens para treinamento

Com a câmera transmitindo, clique em Coletar foto da câmera. Você pode
adicionar uma observação sobre EPIs e condições de iluminação.

Arquivos são salvos em amostras_epi/pendentes:

- JPG original, sem caixas e textos adicionados pelo monitoramento.
- JSON com data, resolução, observação e previsões apenas como referência.

As imagens coletadas não entram automaticamente no dataset, não são
rotuladas automaticamente, não disparam e-mail e não iniciam treinamento.
Revise e anote cada imagem antes de incluí-la no dataset. Separe cenas
relacionadas para evitar colocar quase a mesma foto em treino e avaliação.
A pasta de coleta está no .gitignore.

O botão fica indisponível sem uma imagem recente. A captura também é
recusada pelo servidor se a imagem estiver há mais de 3 segundos sem atualizar.

## Organização do código e testes

- main.py: câmera, inferência, rotas, coleta e notificações.
- epi_monitoramento.py: associação, IDs temporários e confirmação temporal.
- templates/index.html e static/: interface e controlador da página.
- tests/test_monitoramento.py: testes sem câmera ou SMTP reais.
- tests/servidor_demo.py: câmera simulada na porta 5001, com e-mail desativado.
- tests/test_painel.mjs: controlador JavaScript com DOM mínimo e HTTP real.

Executar testes Python:

    .\.venv\Scripts\python.exe -m unittest discover -s tests -v

Para o teste do controlador, inicie o servidor simulado em outro terminal:

    .\.venv\Scripts\python.exe tests/servidor_demo.py

Depois:

    node --test tests/test_painel.mjs

O teste do controlador usa fotos sintéticas temporárias. Ele não substitui
a conferência visual no navegador nem a avaliação com funcionários reais.
Nesta implementação passaram 20 testes Python e o teste do controlador
JavaScript. Uma passagem offline com YOLO e MediaPipe reais também gerou
um quadro, detectou uma pessoa e carregou as cinco classes de EPI, sem
usar a câmera ou enviar notificações.
A verificação visual desta implementação foi bloqueada pela ferramenta de
controle do computador, que não conseguiu confirmar a URL da janela.

## Backup e retorno

A versão anterior foi copiada antes das alterações para:

    backups/monitoramento_antes_confirmacao_20261019/

Essa pasta contém main.py, .env.example e .gitignore anteriores. Para voltar
ao comportamento anterior, pare o servidor e reponha o main.py desse backup
na raiz do projeto. Os novos módulos e arquivos de interface podem permanecer
na pasta, pois o main.py anterior usa a página embutida.

O .env com credenciais e os modelos treinados não foram alterados.

## Ajuste de óculos em 19/10/2026

As capturas enviadas mostravam dois problemas: a confiança do epi.pt para
óculos ficava abaixo de 0,5 e a associação aceitava o item apenas na faixa
superior de 40% da pessoa. Em um close de rosto, os olhos podiam ficar fora
dessa faixa.

Agora a associação usa a posição dos olhos, obtida por detecção local do
rosto. Rosto cortado, quase de perfil ou evidência fraca não confirma
ausência. Uma indicação de óculos com confiança entre 0,15 e 0,5 deixa
a avaliação inconclusiva, sem comprovar que o item foi usado.
Para marcar presença, o limite continua em 0,5 e a caixa precisa coincidir
com a região dos olhos.

O modelo antigo treinamento_epi-2 é utilizado como uma segunda verificação
apenas da classe óculos. A seleção e o limite dos demais EPIs são mantidos.
O modelo principal epi.pt não foi substituído.

É possível configurar outro modelo adicional no .env:

    OCULOS_MODEL_PATH=runs/detect/treinamento_epi-2/weights/best.pt

Reinicie o servidor após uma alteração. Com óculos selecionado, o painel
informa quando a verificação adicional está ativa.

Validação offline com os recortes da câmera nas cinco capturas fornecidas:

| Imagem | Conteúdo observado | Resultado corrigido |
| --- | --- | --- |
| 1 | Com óculos | Detectado |
| 2 | Com óculos, de frente | Detectado |
| 3 | Com óculos, rosto virado/cortado | Inconclusivo, sem alerta |
| 4 | Sem óculos | Possível ausência |
| 5 | Com óculos | Detectado |

O fluxo foi exercitado em três observações por imagem com tempo de
confirmação acelerado para o diagnóstico; os testes unitários verificam
separadamente a confirmação normal de três segundos. Não houve acesso à
câmera nem envio de e-mail. Os recortes não foram usados para treinamento
e não constituem um conjunto independente de avaliação.

Diagnósticos locais estão em diagnosticos/oculos_20261019, fora do Git.
O código anterior a esse ajuste está em backups/antes_ajuste_oculos_20261019.
Para retornar, pare o servidor e reponha main.py e epi_monitoramento.py
desse backup. Nenhum peso de modelo nem credencial foi alterado.

## Correção da avaliação de quedas em 20/10/2026

A regra anterior classificava praticamente todo tronco com inclinação de até
60 graus como em pé, a menos que a caixa da pessoa fosse muito larga.
Inclinações intermediárias, pontos coincidentes e algumas leituras inválidas
podiam acabar rotuladas como em pé. Também eram exigidos os dois lados do
tronco, prejudicando a avaliação de pessoas deitadas de lado.

Agora:

- Os marcos precisam ser finitos, visíveis e separados por uma distância mínima.
  Um lado do tronco suficientemente visível permite a avaliação lateral; lados
  contraditórios deixam a postura inconclusiva.
- A inclinação é calculada em pixels, considerando largura e altura reais,
  inclusive quando a câmera entrega uma resolução diferente da solicitada.
- A faixa de até 30 graus pode indicar em pé. A partir de 55 graus pode indicar
  deitada; entre 45 e 55 graus também se exige caixa mais larga, com proporção
  de pelo menos 1,15. As demais situações ficam inconclusivas. Uma caixa larga
  sozinha não comprova queda. Pernas verticais visíveis em uma caixa alta podem
  indicar uma pessoa curvada, deixando a leitura inconclusiva.
- A pose recebe uma margem de 15% ao redor da pessoa. Os marcos retornam ao
  referencial da caixa original, preservando a associação dos EPIs.
- A confirmação usa o instante da obtenção do quadro. A tolerância entre
  observações acompanha o processamento medido, limitada a 10 segundos;
  não se confunde automaticamente uma pausa da câmera com processamento lento.
- O painel mostra inclinação estimada, motivo de leitura inconclusiva e
  progresso em quadros/segundos da confirmação. Há um aviso de processamento
  lento acima de 2 segundos por quadro.

Esses limiares são heurísticos, não uma calibração validada no ambiente do
outro computador. O sistema continua alertando **possível queda por postura
deitada persistente**, não comprovando um movimento de queda nem um acidente.
Não foi realizado treinamento novo e os modelos de EPI não foram substituídos.

Posicione a câmera aproximadamente nivelada e com o corpo inteiro visível.
Uma pessoa deitada em direção à câmera pode parecer vertical na imagem 2D;
vistas de cima, oclusões e enquadramentos cortados também exigem avaliação real
da instalação. Nesses casos, envie uma captura do painel e os valores de
inclinação/quadros por segundo para diagnosticar a cena. Não simule uma queda
perigosa: use imagens ou uma pessoa já deitada em uma posição segura.

Validação automatizada: 46 testes Python, incluindo geometrias sintéticas em
resoluções diferentes, pose ausente/contraditória, pessoa curvada e uma câmera
simulada com 3 segundos de inferência por quadro. Isso não constitui uma
avaliação de precisão com quedas reais. O controlador JavaScript também testa
a apresentação da postura inconclusiva e do progresso de confirmação.

Backup anterior ao ajuste:

    backups/antes_correcao_quedas_20261020/

Para retornar localmente, pare o servidor e restaure main.py,
epi_monitoramento.py e static/painel.js desse backup. As credenciais e os pesos
dos modelos permaneceram inalterados. No GitHub, o commit anterior ao ajuste
de quedas é b89b7e2, que preserva a versão publicada em 19/10/2026.

## Reanálise local de EPIs em 20/10/2026

Este ajuste foi inicialmente aplicado somente no computador de origem, conforme
solicitado. Sua publicação no GitHub foi autorizada em 21/10/2026 e está incluída
nesta versão. Foi preservado o estado anterior localmente em:

    backups/antes_ajuste_distancia_epi_20261020/

Nas duas capturas recebidas havia capacete visível, mas o modelo principal não
o detectava no quadro inteiro em tamanho de inferência 640. A segunda análise,
usando a caixa da pessoa detectada automaticamente, encontrou o capacete com
pontuações de 0,6703 e 0,7620. Essas são pontuações do detector, não porcentagens
de precisão nem probabilidades calibradas de uso correto.

O sistema continua analisando o quadro inteiro. Quando um EPI selecionado não
está associado à pessoa, analisa também um recorte dela em tamanho 640, com
pequena margem. As coordenadas retornam ao quadro original para a associação
normal entre pessoa e EPI. Previsões sobre vizinhos fora da caixa são
descartadas; associações ambíguas continuam inconclusivas. Não houve troca de
pesos nem treinamento novo.

Há limite de quatro pessoas reanalisadas por quadro, em rodízio. Quem estiver
aguardando reanálise não terá ausência confirmada apenas porque o item não
apareceu na imagem inteira. Uma falha nessa etapa também deixa a avaliação
inconclusiva e não desliga a câmera nem a análise de quedas. A interface mostra
o número de reanálises, pendências e eventuais falhas. Mais de quatro pessoas
podem manter leituras inconclusivas por falta de observações consecutivas;
esse limite protege o processamento e não garante monitoramento simultâneo de
qualquer quantidade de funcionários.

O limite para marcar presença permanece 0,5. Na reanálise, indicações entre
0,25 e 0,5 para capacete, colete, luvas ou máscara deixam a leitura inconclusiva;
não são promovidas a presença nem confirmam ausência. Para óculos continua
valendo o piso de 0,15 para evidência fraca. A análise global mantém seus limites
anteriores. A chamada global reinicia explicitamente o filtro de classes, para
não herdar a seleção usada no recorte da pessoa no quadro anterior.

Também há limites de detalhe na imagem original para avaliar ausência:

- Capacete: olhos visíveis e separados por pelo menos 12 pixels, além dos
  demais requisitos de visibilidade.
- Colete: separação dos ombros de pelo menos 36 pixels e comprimento do tronco
  de pelo menos 40 pixels.
- Luvas: pelo menos 12 pixels entre os marcos de pulso e dedo de cada mão.
- Máscara e óculos: permanecem as regras específicas de visibilidade facial.

Esses valores são filtros conservadores de pixels, não uma distância em metros
validada. Um recorte ajuda o modelo a usar melhor o detalhe existente, mas não
recupera informação que a câmera não capturou. Isso pode aumentar os estados
inconclusivos; inconclusivo não significa que o funcionário esteja usando EPI.
Para maior alcance ainda é necessário avaliar resolução, iluminação,
enquadramento e dados reais de treinamento para cada item. Os modelos atuais
não foram validados para uma distância operacional máxima.

Validação: 60 testes Python e o teste do controlador JavaScript passaram.
Foi exercitado o fluxo completo com três observações de cada captura fornecida:
as duas retornaram capacete presente, sem alertas. Câmera e envio de alertas
foram simulados; o tempo normal de confirmação é coberto pelos testes unitários.
Essas imagens foram usadas para desenvolver o ajuste e não são um conjunto
independente de avaliação, nem uma medição de desempenho em longa distância.

Scripts e relatórios locais estão em diagnosticos/epi_distancia_20261020/.
Nenhuma foto, senha ou modelo foi enviado para o GitHub. A documentação de
[inferência do Ultralytics](https://docs.ultralytics.com/modes/predict/)
explica os parâmetros de tamanho, confiança e classes utilizados.

Para aplicar, reinicie o servidor e atualize o navegador com Ctrl+F5. Para voltar,
pare o servidor e restaure main.py, epi_monitoramento.py e static/painel.js
do backup acima. epi_inferencia.py pode permanecer, pois o main.py anterior não
o importa. Não é necessário alterar .env, instalar dependências ou substituir
modelos para usar este ajuste.

## Óculos com pouca evidência e rótulos em 21/10/2026

Ajuste inicialmente local, posteriormente autorizado para publicação no GitHub
em 21/10/2026 e incluído nesta versão. Backup anterior ao ajuste, disponível
somente no computador de origem:

    backups/antes_ajuste_oculos_inclinados_20261021/

Foram reproduzidas as duas novas fotos pelo fluxo real, substituindo somente a
câmera, o relógio e o envio de alertas por simulações. A primeira tem capacete e
óculos; a segunda tem óculos, mas não tem capacete. Os modelos atuais não
reconhecem esses óculos com confiança suficiente nessas condições. Testar o
quadro em tamanho 1280 e recortes do rosto também não produziu uma detecção
forte. Portanto, este ajuste reduz falsos alertas, mas NÃO resolve o treinamento
nem transforma essas duas leituras em óculos presentes.

Mudanças:

- O detector auxiliar de óculos agora também recebe o recorte da pessoa quando
  o quadro inteiro e o detector principal não comprovam presença. Antes, só o
  principal recebia esse recorte. O auxiliar continua restrito à classe óculos;
  seus outros EPIs não passam a regularizar a pessoa.
- Continua o limite de quatro pessoas reanalisadas por quadro, em rodízio.
  Cada uma pode exigir até duas inferências locais, principal e auxiliar.
  Uma presença forte já associada evita a chamada seguinte. Isso pode reduzir
  o FPS; o aviso de processamento lento permanece ativo.
- A falta de detecção só permite iniciar confirmação de ausência de óculos
  quando há pelo menos 48 pixels entre os marcos dos olhos na imagem ORIGINAL,
  além dos demais filtros de visibilidade e reanálise. Nas fotos novas há
  aproximadamente 46,9 e 44,5 pixels. O filtro anterior de 12 pixels continua
  na referência usada para associar uma detecção positiva, não para comprovar
  ausência. O valor 48 é uma restrição operacional conservadora motivada pelas
  falhas observadas, não um limite de alcance ou uma precisão validados.
  Ela também pode deixar casos realmente sem óculos inconclusivos.
- O limite de presença permanece 0,5; indícios entre 0,15 e 0,5 não são
  promovidos a presença. Falha ou pendência de reanálise do auxiliar não
  comprova ausência. Se o auxiliar configurado não carrega ou falha no quadro
  inteiro, a ausência de óculos também não é confirmada nesse estado.
- Para associar óculos, a caixa prevista precisa estar junto à linha dos
  olhos, não somente ter o centro próximo. Isso impede que uma detecção
  restrita à testa conte como óculos usados sobre os olhos.
- O status e os cartões do painel explicam o motivo por item inconclusivo.
  A imagem usa amarelo para incerteza/verificação, verde para leitura sem
  pendências e vermelho para alertas confirmados. Inconclusivo não significa
  EPI presente. Rótulos foram separados em linhas e reposicionados para evitar
  cortar o texto na borda direita nas capturas fornecidas.
- A postura não foi forçada para "Em pé": quando ombros/quadris não permitem
  avaliar o tronco, continua inconclusiva. Não há evidência de queda nessas
  duas imagens estáticas; elas não validam a detecção de quedas em movimento.

Resultado nas duas fotos novas: capacete presente na primeira; possível
ausência de capacete na segunda; óculos inconclusivos nas duas, sem falso
alerta de óculos. Nos cinco exemplos anteriores, três presenças de óculos,
um perfil inconclusivo e uma possível ausência no rosto sem óculos foram
preservados. As duas fotos anteriores com capacete também continuam positivas.
Essas imagens orientaram o ajuste e não são um conjunto independente de teste.

Verificação: 79 testes Python (incluindo regressões de quedas, Flask,
confirmação, associação e falhas dos detectores), quatro testes JavaScript de
apresentação em memória e verificação de sintaxe JavaScript passaram. O teste
JavaScript completo com servidor HTTP separado não foi reexecutado: a ferramenta
bloqueou o comando de gerenciamento desse processo de teste. Nenhuma câmera
real foi aberta e nenhum e-mail foi enviado. Scripts e resultados privados:

    diagnosticos/epi_oculos_20261021/

Não houve novo treino, troca de pesos, instalação de pacotes ou mudança em
.env. Para melhorar o reconhecimento, ainda é necessário coletar/anotar dados
reais com e sem os óculos, incluindo capacete, inclinações e distâncias da câmera,
e avaliar com vídeos separados por pessoa/cena. O sistema atual não deve ser a
única medida de segurança nem justificar punições automáticas.

Para aplicar, reinicie o servidor e recarregue o painel com Ctrl+F5. Para voltar,
pare o servidor e restaure main.py, epi_inferencia.py, epi_monitoramento.py e
static/painel.js do backup acima. Os testes e esta documentação também foram
preservados no backup; os dois arquivos novos de teste podem permanecer sem
alterar o funcionamento do aplicativo. Para testar a versão restaurada, arquive
test_oculos_limites.py e test_painel_oculos.mjs fora de tests/, pois eles dependem
deste ajuste. Nenhuma credencial ou foto foi publicada.

### Atualização do repositório em 21/10/2026

Esta publicação inclui o código de reanálise de EPIs de 20/10 e o ajuste de
óculos de 21/10, com seus testes automatizados. Não inclui os backups,
diagnósticos com fotos, .env, configurações privadas ou a .venv do computador
de origem. As dependências, o YAML portátil e os três modelos publicados
anteriormente foram preservados.

Para atualizar outro computador, pare o servidor e, em um clone sem alterações
locais pendentes, execute git pull --ff-only. Reinicie o aplicativo e atualize
o navegador com Ctrl+F5. O .env e a política privada permanecem locais. Quem
precisar voltar à versão publicada antes dos ajustes de EPI pode consultar o
commit d30462b; os backups citados acima não são distribuídos no repositório.
