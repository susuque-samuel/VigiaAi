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
Uma perda de detecção interrompe a confirmação. Intervalos maiores que
2 segundos entre observações também reiniciam a contagem.

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
