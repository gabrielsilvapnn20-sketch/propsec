---
name: prospectar
description: Rodar uma sessão de prospecção de influenciadoras no Instagram pelo Claude in Chrome — encontrar perfis seguindo as sugestões a partir de perfis bons, analisar e salvar no PropSec. Use quando o usuário pedir para prospectar, buscar perfis, achar influenciadoras ou rodar o agente.
---

# Sessão de prospecção

Você navega no Instagram com a conta de prospecção (já logada no Chrome) e salva perfis no
PropSec. **Só leitura:** nunca envie mensagem, siga, curta, comente, reaja ou responda story.
Antes de usar o navegador, carregue a skill `anthropic-skills:chrome-browser`.
Trabalhe numa aba nova do Chrome; não mexa nas outras abas.

## Regras de segurança (obrigatórias)

1. **Antes de abrir CADA perfil**, rode o porteiro com timeout de 10 minutos
   (`timeout: 600000` na ferramenta Bash), porque ele pode esperar alguns minutos:
   ```bash
   python propsec.py liberar @perfil
   ```
   `LIBERADO` → pode abrir. `PARAR: ...` → encerre a sessão (passo 5) e diga o motivo ao
   usuário. Não contorne, não espere por conta própria, não abra "só mais um".
2. Qualquer sinal de alerta do Instagram (login/verificação, captcha, "tente mais tarde",
   "ação bloqueada", "atividade incomum", deslogou, páginas que não carregam) →
   `python propsec.py alerta "o que apareceu"`, encerre e avise o usuário.
3. Se o usuário pediu N perfis, pare em N.

## 1. Abrir a sessão

```bash
python propsec.py sessao inicio
python propsec.py exemplos
python propsec.py proximas-fontes 20     # use o número de perfis pedido pelo usuário
```
**Leia `exemplos` com atenção antes de começar:** são perfis reais que o usuário fechou,
destacou, aprovou e descartou. Sua nota de estilo deve imitar o gosto dele, não o seu.
Se `sessao inicio` disser BLOQUEADO, não comece: diga o motivo.

**Tamanho da conversa:** cada perfil analisado enche a memória da conversa (capturas de tela,
textos), e a conversa fica cada vez mais lenta. Faça no máximo ~20 perfis por conversa. Ao
terminar, diga ao usuário para abrir uma **conversa nova** para a próxima sessão.

**Comandos:** use sempre `python propsec.py ...` sozinho, sem `echo ... |`, `&&` ou `cd`
na frente, para que um único padrão de permissão cubra todos.

## 2. Equilíbrio: seguir a linha e explorar

O plano de `proximas-fontes` divide a sessão em três partes — respeite as proporções:
- **A. Linha aprovada (~50%)** — sugestões a partir de fechadas, aprovadas e referências.
- **B. Potencial (~20%)** — sugestões a partir de achados novos com nota boa que o usuário
  ainda não avaliou (bola de neve para fora da rede).
- **C. Exploração (~30%)** — cidades do interior, lojas (aba Marcados), hashtags e buscas,
  sorteadas para variar. Aqui o objetivo é **descobrir estilos novos**: salve também perfis
  diferentes das aprovadas (estilo ≥ 0.5) se tiverem sinais de público real (comentários de
  gente da cidade, "seguido por" locais, publi de lojas da região) e escreva
  "exploração: <o que é diferente>" nas observações.

Os `exemplos` mostram o gosto do usuário, mas são **guia, não filtro**: não descarte um
perfil só porque não se parece com as aprovadas. É o usuário quem decide na fila; os perfis de
exploração que ele aprovar viram novos caminhos.

## 2.1 Como seguir sugestões a partir de um perfil

O usuário quer **perfis parecidos com os que já deram certo**, achados pelas sugestões do
próprio Instagram. `proximas-fontes` lista as **sementes** (fechadas, aprovadas, referências).

1. Abra uma semente. Ao lado de "Enviar mensagem" há o botão de **perfis semelhantes**
   (ícone de pessoa com "+"). Clique: aparece a faixa de sugestões. Role a faixa para ver mais.
2. Anote **todos** os @ das sugestões. Só pule o que é claramente loja, página/empresa
   ou homem. **Não julgue pela foto pequena ou pelo nome**: muitas boas só aparecem quando
   você abre o perfil. O usuário quer que você entre em cada sugestão.
3. Verifique em lote quais são novos: `python propsec.py existe @a @b @c ...`
   (pule `JA_EXISTE`: já estão no sistema ou já foram contatadas pelo usuário).
4. Abra e analise **cada uma** das novas, uma por vez (passo 3), sem pular.
5. **Bola de neve:** quando uma nova for boa (nota ≥ 60), use-a como semente também e abra as
   sugestões dela. Assim você sai da rede conhecida.
6. Registre cada semente usada: `python propsec.py fonte sugestoes nome_da_semente --vistos N`.
   Salve os perfis com `"origem": "sugestoes", "origem_detalhe": "nome_da_semente"`.
7. **Se o usuário indicar por onde começar** ("comece pela @x", "explore Bacabal"), siga o
   pedido dele em vez do plano.

**Não use agências** (fly.creators.br, hub.influ.br e parecidas) como fonte: quem elas
seguem já é agenciado. Se um perfil mostrar "Seguido(a) por" uma agência, anote isso nas
observações ("possivelmente agenciada"), mas pode salvar.

**Complemento (no máximo 1/3 da sessão):**
- **Lojas locais de moda/beleza** (boutiques, calçados, salões, cosméticos de cidades
  pequenas): abra a aba **Marcados** da loja. Quem aparece ali fazendo provador/recebidos
  costuma ser exatamente a "blogueira da cidade" que fecha permuta. Ache a loja pela busca
  ("boutique Codó", "loja feminina Bacabal") e registre: `fonte pagina_local "<@loja>" --nota "cidade"`.
  Lojas sem público feminino (móveis, mercado, farmácia grande) não servem.
- Cidades e hashtags do bloco 2 de `proximas-fontes`, principalmente quando as sugestões
  começarem a repetir perfis já vistos.

## 3. Analisar um perfil — modo volume

O nicho vive de **volume**: quase toda "blogueira" compatível é oportunidade. O que decide é
o **estilo** (parecer com as fechadas) e a **faixa de seguidores**. Reels bombando é bônus,
não requisito. **Olhe cada perfil com calma** (1 a 3 minutos é normal): o usuário prefere
análise cuidadosa a pressa. Só não fique parado sem agir — se estiver em dúvida, salve com
uma observação explicando a dúvida e deixe o usuário decidir na fila.

**Passo único (obrigatório):** `liberar` → abrir o perfil → ler o topo (seguidores, nome,
bio, categoria, destaques) → rolar a grade uma ou duas vezes. Se a aba **Reels** estiver a um
clique, abra e anote a mediana das views que aparecem na grade. Abra alguns posts e leia os
comentários quando ajudar a entender o perfil e quem acompanha ela.

**Stories (importante — só para quem passou na triagem de seguidores e estilo):**
se a foto de perfil tiver o **anel colorido**, clique nela e assista os stories do dia.
- Pause (botão de pausa no topo do story) para ler cada um e avance com a seta da direita.
  Veja no máximo 15; feche com o X.
- Conte `stories_qtd` (quantos tinha) e quantos eram **divulgação** de loja/marca/serviço
  (marca @loja, mostra produto com preço, "cupom", "link", "corre lá", provador, recebido,
  sorteio de loja) → `stories_publi` = divulgação ÷ total.
- O que **não** é divulgação: rotina, filhos, casa, humor, desabafo, rolê, caixinha de
  perguntas, foto dela.
- **Nunca** curta, reaja, responda, use caixinha/enquete ou envie mensagem pelo story.
  Só assistir.
- Sem anel: não abra destaques um por um; só leia os títulos dos destaques (ex.: vários
  destaques "Parceria X", "Loja Y" indicam perfil de divulgação).
Atenção: a conta de prospecção aparece na lista de quem viu o story — isso é esperado.

**Nota de estilo (`estilo_blogueira`, 0 a 1)** — compare com as fechadas:
- **1.0** — igual às fechadas: mulher, selfies/looks/rotina, se apresenta como blogueira/
  criadora ou "parcerias no direct", stories/destaques ativos, cara de conhecida na cidade.
- **0.7** — perfil pessoal ativo de mulher, "paga de blogueira", mas sem falar em parceria.

**Atenção a um viés:** foto de celular, casa simples, conteúdo de comunidade/periferia,
"baixa renda", português informal **não** baixam a nota. Esse público costuma ser muito
fiel e já deu lucro altíssimo (veja os destacados em `exemplos`). Não premie "produção
bonita"; premie **ser conhecida e ter gente de verdade interagindo** (comentários de amigas,
vizinhas, clientes; "seguido por" gente da mesma cidade).
- **0.4** — perfil pessoal comum, poucos sinais de blogueira.
- **0–0.2** — não é o estilo: loja, página, homem, empresa, perfil abandonado, famosa grande.

**Público popular (`publico_popular`, 0 a 1)** — o produto é para público **popular**
("baixa renda"). Perfis de público universitário/classe média raramente servem, mesmo
parecendo blogueira. Julgue pelo **conteúdo e estilo de vida mostrados**:
- **1.0** — rotina simples, humor do dia a dia, bairro/comunidade/cidade pequena, forró,
  paredão, festas locais, filhos, casa, linguagem informal, foto de celular, comentários de
  amigas e vizinhas.
- **0.5** — misto: blogueira de cidade com alguns sinais de vida mais "arrumada".
- **0–0.2** — faculdade/profissão na bio (enfermagem, medicina, med vet, odonto, direito
  etc.), ensaios fotográficos e poses editoriais, link de VSCO/portfólio, "lifestyle |
  outfits" aspiracional, clube de corrida/academia premium, viagens e restaurantes caros,
  perfil pessoal que não é blogueira.
**Nunca** use cor da pele, traços, cabelo, corpo ou aparência física para esta nota — só o
que a pessoa mostra de rotina, lugares, interesses e como se comunica.

**Perfil comercial (`perfil_comercial`, 0 a 1)** — o usuário raramente fecha com quem
**vive de divulgar** (stories tomados por lojas de sapato, perfume, roupa da cidade, várias
marcas) ou é **dona de negócio com muitas clientes** (loja de roupa, maquiagem, unha, salão).
Escrever "publi"/"parcerias" na bio **não** é problema; o problema é a quantidade de
divulgação no dia a dia.
- **1.0** — a maior parte dos stories/feed é divulgação de várias lojas e marcas, ou é dona de
  negócio com muitas clientes.
- **0.5** — divulga com frequência, mas ainda posta muita coisa pessoal; ou tem negócio
  próprio **pequeno** (poucas clientes, começando) — ainda pode fechar.
- **0–0.2** — perfil pessoal; divulgação de vez em quando.
Isso reduz a nota (os números de stories também entram na conta sozinhos); não é motivo para
ignorar, exceto quando é 1.0 e o estilo não é forte.

**Salvar como `novo`** se estilo ≥ 0.6, público popular ≥ 0.4 **e** seguidores entre 1.000 e 30.000 (ideal
3.500–15.000; de 15.000 a 30.000 só se o estilo for 0.85+). **Acima de 30.000: `ignorado`**
("acima de 30k") — o usuário não fecha com perfis grandes, mesmo que estejam nas referências.
Caso contrário, salve como `ignorado` com o motivo (para não revisitar). Seguidores comprados
(milhares de seguidores, curtidas/views ínfimas, comentários de bot) → `ignorado`.

Colete o que estiver **visível sem esforço**: `seguidores`, `seguindo`, `posts`, `nome`,
`bio`, `cidade`/`uf`, `estilo_blogueira`, `publico_popular`, `perfil_comercial`, `stories_qtd`,
`stories_publi`, `stories_ativos` (anel colorido ou destaques
recentes), `faz_publi` (publi/recebidos/lojas marcadas visíveis), `contato`, `link_bio`,
`publicos` (mãe, maternidade, mulher de preso, moda, beleza, humor, forró, praia,
lifestyle, interior...), `media_views_reels` se viu, e `observacoes` com 1 frase de por que
lembra as fechadas. Campo que você não viu: **omita**.

```bash
python propsec.py salvar - <<'JSON'
{"username": "maria.blog", "nome": "Maria", "cidade": "Codó", "uf": "MA",
 "seguidores": 6200, "seguindo": 900, "posts": 41, "estilo_blogueira": 0.9, "publico_popular": 0.9, "perfil_comercial": 0.2,
 "stories_qtd": 7, "stories_publi": 0.15,
 "stories_ativos": 1, "faz_publi": 1, "bio": "...", "publicos": ["mãe", "moda"],
 "media_views_reels": 4800,
 "observacoes": "mãe, looks e provador de loja local, parcerias no direct",
 "origem": "sugestoes", "origem_detalhe": "joicimara"}
JSON
```

Se o usuário pedir **modo detalhado**, além disso abra 2–3 posts/reels e colete
`media_curtidas`, `media_comentarios` e `comentarios_reais` (0 a 1).

**O que as fechadas têm em comum** (`referencias/referencias_iniciais.json`): categoria
"Blogueiro(a)"/"Criador de conteúdo digital", "parcerias no direct", muitas são **mães**,
**poucos posts no feed é normal** (6–31 posts deram resultado), stories ativos, seguem muita
gente, selfies/looks/praia, reels de POV com frase, humor do dia a dia, forró; Nordeste/Norte
e cidades pequenas. Perfis "não tão bons no papel" já deram resultado alto.

## 4. Navegar como uma pessoa

- Chegue nos perfis **clicando** (sugestões, busca), não digitando `instagram.com/usuario`
  em sequência.
- Role aos poucos; não pule direto para o fim. Varie a ordem dos passos.
- De vez em quando (1 a cada 6–8 perfis), volte para o feed ou Explorar por alguns segundos.
- Um perfil por vez, uma aba só. O ritmo entre perfis é do porteiro.

## 5. Encerrar

```bash
python propsec.py fonte sugestoes "<@semente>" --vistos <n>     # para cada semente usada
python propsec.py sessao fim --visitados <total> --salvos <salvos sem ignorados>
python propsec.py resumo
```
Responda ao usuário: quantos perfis viu, quantos bons salvou, os 5 melhores (@, cidade,
seguidores, views médias dos reels, por que vale) e quais sementes renderam mais.
A fila para aprovar fica em http://localhost:8000/fila.
