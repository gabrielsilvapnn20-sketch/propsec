# PropSec — prospecção de influenciadoras

## A operação
Buscamos influenciadoras **de menor porte** no Instagram para parcerias:
- Faixa principal: **1.500 a 10.000 seguidores**. Casos especiais: até 15.000–20.000.
- O que mais importa: **views nos stories**. Ninguém de fora vê isso, então usamos sinais
  públicos que andam junto: views dos reels ÷ seguidores, engajamento, comentários de gente
  real, constância, stories ativos.
- Prospecção **aberta**: muitas "pagam de blogueira" — público pequeno mas ativo, conhecida na
  cidade/região, interage, às vezes já faz outras parcerias. Forte no **Maranhão** (cidades do
  interior incluídas), mas não só.
- Públicos específicos (mãe solo, mulher de preso, maternidade etc.) são **etiquetas**, não
  filtros. Não restringir a busca a eles.
- Recusar ou não responder **não** torna um perfil ruim. Perfis bons que recusaram são
  referência do tipo `gostamos`.

## Resultado = lucro por dia
O que define uma parceria boa é o **lucro no dia** que ela gera. Referências (15 fechadas, em
`referencias/referencias_iniciais.json`): `alto` = mais de R$ 1.000 em um dia (gauannelacerda,
tamillymacedo_, samara_reggina_, lay_ruivinha288); `medio` = R$ 200–500/dia (as outras 11).
Registrar sempre o lucro (`--lucro`) ou o nível (`--resultado`) das novas parcerias: é o rótulo
mais forte do aprendizado. Perfis "não tão bons" no papel já deram resultado alto.

## Já contatados e horizonte
O usuário chama perfis por fora; quando ele mandar uma lista, registre com
`python propsec.py contatados @a @b ...` (ou `--arquivo lista.txt`). A rede das referências
(agências, "seguido por") já foi muito trabalhada: no máximo 1/3 de cada sessão vem dela;
o resto é horizonte novo (achados fora da rede, páginas locais, cidades novas).

## Regras do agente
- No Instagram **só leitura**: nunca enviar mensagem, seguir, curtir, comentar, reagir.
  As mensagens são enviadas pela equipe, fora do agente.
- Conta exclusiva de prospecção. **Antes de abrir cada perfil: `python propsec.py liberar @x`**
  (timeout 10 min). `PARAR` → encerrar a sessão. Navegar clicando e rolando, como pessoa.
- Qualquer bloqueio/captcha/aviso do Instagram → `python propsec.py alerta "..."`, parar e avisar.
- Limites e botão PARAR: http://localhost:8000/seguranca (o usuário controla).
- Não inventar números. Campo não visto = omitir.
- Guardar só dados públicos e profissionais do perfil.

## O sistema
- `propsec.py` — linha de comando (salvar, existe, fonte, proximas-fontes, status, recalibrar...).
- `app/` — banco SQLite (`dados/propsec.db`), nota (`scoring.py`), aprendizado
  (`aprendizado.py`) e painel web (`web.py`, http://localhost:8000).
- Funil: novo → aprovado/descartado → contatado → respondeu → negociando → fechado
  (ou recusou / sem_resposta). `ignorado` = o agente viu e não serve (não entra no aprendizado).

## Skills
- `prospectar` — sessão de busca no Instagram via Claude in Chrome.
- `cadastrar-referencias` — prints/perfis já fechados ou que gostamos.
- `recalibrar` — relatório e reajuste dos pesos.

Use `python` (no Windows pode ser `py`). Rode os comandos a partir da pasta do projeto.
