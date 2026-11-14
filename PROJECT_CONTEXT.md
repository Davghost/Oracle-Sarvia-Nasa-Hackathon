# PROJECT_CONTEXT.md — The Algorithm's Oracle

> **Memória compartilhada do projeto.** Qualquer agente de IA ou integrante deve ler este arquivo inteiro antes de trabalhar e **atualizar a seção 13 e o log (seção 15)** depois de qualquer decisão.
> Última atualização: **14/11/2026, ~12:00 (horário de Brasília)** · Versão **0.2**

Legenda de confiança usada neste documento:
- **[CONFIRMADO]** vem de fonte oficial (NASA / Space Apps / ASF) ou da própria equipe.
- **[TERCEIROS]** vem de fonte não oficial; usar com cautela.
- **[HIPÓTESE]** ideia ou suposição nossa, ainda não verificada.
- **[A VERIFICAR]** fato necessário para o projeto que ainda não foi checado.

---

## 1. Resumo em 5 linhas

- Evento: **NASA Space Apps Challenge 2026**, desafio **"Dancing with the SARs"**, equipe **The Algorithm's Oracle** (3 pessoas).
- Vamos construir um **site interativo (Flask)** que mostra uma **cheia real em Moçambique (janeiro de 2026)** vista pelo radar **NISAR (L-band)**.
- Núcleo (MVP): mapa antes/durante com **área alagada detectada pelo radar** e números (km²).
- Diferenciais (fases seguintes): validação contra outro produto, vias bloqueadas e **rota segura** para equipes de resgate, texto explicativo por IA.
- **Prazo duro: domingo 15/11/2026, 23:59, horário local do nosso Local Event** [A VERIFICAR qual é o fuso]. Meta interna: enviar até **21:00**.

---

## 2. O desafio

**Título:** Dancing with the SARs · Dificuldade: intermediária/avançada · Área: Earth Science. [CONFIRMADO — texto oficial colado pela equipe]

**Pedido central (paráfrase do enunciado oficial):** construir uma **aplicação interativa** que use dados de radar do **NISAR** (NASA-ISRO) para **rastrear e visualizar um ou mais tipos de mudança de superfície**, em locais do mundo.

**O que o enunciado deseja como resultado:** uma solução **de código aberto e fácil de usar** que traduza observações complexas de radar em informação útil para cientistas, gestores, educadores, tomadores de decisão e público. Exemplos citados: mapas interativos de mudança, animações de séries temporais, painéis (dashboards).

**Passos sugeridos pelo enunciado:** (1) escolher uma área de estudo; (2) baixar dados NISAR gratuitos; (3) usar dados complementares (óptico, camadas GIS) para dar contexto; (4) apresentar os resultados em mídia digital interativa; (5) **levantar hipóteses sobre os fenômenos físicos** que causam o que se vê (ou não se vê) no radar; (6) discutir quais polarizações destacam as mudanças e aplicações futuras do NISAR.

**Considerações opcionais citadas:** várias polarizações e/ou frequências, séries temporais com várias datas, dados auxiliares (população, vegetação), mostrar impacto humano, **storytelling** com visualizações, contexto pessoal da área, resumo interativo (sliders, mapas web).

**Nossa interpretação:** o desafio **não exige** IA, previsão ou cobertura global. Exige **interatividade, dados NISAR reais, clareza e comunicação**. Quem entrega isso bem, funcionando e bem contado, pontua em Relevância, Validade e Apresentação.

---

## 3. Regras do evento e da submissão (resumo operacional)

Fontes: páginas oficiais do Space Apps (guia de submissão, guia de julgamento, FAQ, termos). [CONFIRMADO, salvo indicação]

| Item | Regra |
|---|---|
| Datas | 14–15/11/2026. Submissão abre sáb 14/11 às 9h e **fecha dom 15/11 às 23:59, horário local do Local Event** (Universal Event: horário do dono da equipe). Sem exceções. |
| Equipe | Até 6 pessoas. **Todos devem estar registrados no mesmo Local Event** (sem lista de espera) para o projeto ser elegível a prêmios. |
| Envio | Botão **"Submit for Judging"** na aba Project da equipe. A submissão é final. |
| Idioma | **Tudo em inglês** no formulário e nos materiais ligados. Vídeo pode ter outra língua, mas **precisa de legendas em inglês**. |
| Demo obrigatória | **Vídeo de até 30 segundos OU até 7 slides.** Passar do limite = **inelegível ao Global Judging**. Hospedar fora (YouTube, Drive, GitHub…) com **link público sem login**. |
| Link do projeto final | Link público (site ou repositório), sem login. |
| Dados NASA | Para concorrer a prêmio global, **é obrigatório usar dados/recursos da NASA**. |
| Uso de IA | **Permitido, mas deve ser declarado.** Imagens/vídeos gerados por IA: **marca d'água visível**. Áudio e código gerados por IA: indicar na descrição e nos metadados. **Não usar logos ou identidade da NASA.** |
| Originalidade | Marcar "trabalho original"; **listar todos os recursos externos** (código, texto, imagens), mesmo livres. Nada com copyright sem permissão. |
| Conteúdo proibido | Promoção comercial, dados pessoais, menores de 18 identificáveis, material sem direitos. |
| Licença | Se não especificarmos, a NASA distribui o conteúdo sob **Apache 2.0**. |
| Critérios de julgamento | **Impacto, Criatividade, Validade, Relevância, Apresentação.** (O guia que consegui abrir é de 2024 e chama o primeiro de "Influence". Conferir o guia 2026, liberado em 13/11.) |
| Participação | Quem submeter no prazo recebe certificado de participação. |

Critérios, em linguagem simples:
- **Impacto:** quanto o projeto pode ajudar e em que escala.
- **Criatividade:** novidade da abordagem.
- **Validade:** é cientificamente correto? Funciona no mundo real?
- **Relevância:** responde ao desafio? Está completo? É utilizável?
- **Apresentação:** a história é bem contada? (O guia oficial pede atenção igual a este critério.)

---

## 4. Problema que decidimos resolver

**Em uma frase:** *quando uma cheia atinge uma região coberta por nuvens, equipes de resposta e comunidades ficam sem ver onde está a água; o radar enxerga através das nuvens, mas os dados são difíceis de usar.*

**Público-alvo (definido pela equipe):** Defesa Civil, Corpo de Bombeiros, equipes de resgate, órgãos públicos e, principalmente, **comunidades em áreas de risco de enchentes e alagamentos**.

**Escopo original da equipe:** prevenção e gestão de enchentes, incluindo previsão de áreas de risco, identificação de regiões afetadas, rotas seguras e otimização de caminhos para resgate.

**Corte de escopo decidido (14/11):** a **previsão de risco** foi **descartada** para este hackathon (o NISAR só tem dados públicos desde 17/06/2026, não há histórico para treinar nada, e não dá tempo). O foco é **detectar e comunicar** a área afetada, e depois, se der tempo, **vias bloqueadas e rota segura**.

---

## 5. Ideia e proposta de solução

**Caso de estudo (DECIDIDO): cheia de janeiro de 2026 em Moçambique**, bacias dos rios **Limpopo e Incomati** (sul do país; cidades-exemplo usadas pela NASA: Chokwe e Macia).

Por que este caso:
- A NASA publicou uma visualização oficial dessa cheia com NISAR (NASA SVS #5661): o radar imageou a região em **5 e 17 de janeiro de 2026**, enquanto o satélite óptico Sentinel-2 só via nuvens. [CONFIRMADO]
- Impacto citado pela NASA: **mais de 600 mil deslocados, ~400 mil acres de lavoura danificados, ~30 mil casas alagadas**. [CONFIRMADO — NASA SVS]
- A história "a nuvem escondeu, o radar viu" é exatamente a vantagem do SAR.
- Produto usado pela NASA: **NISAR GCOV** (retroespalhamento polarimétrico). Composição falsa-cor da NASA: HH em vermelho, HV em verde, razão em azul; azul escuro = água aberta, magenta = floresta alagada, verde = copa/volume. [CONFIRMADO]

**Como funciona (visão simples):**
1. Baixamos 2 (ou mais) cenas NISAR GCOV da mesma trilha/direção: **antes** e **durante** a cheia.
2. Um **script offline** recorta a área, converte para dB, identifica água (água aberta é escura no radar), subtrai a água permanente e calcula a **área alagada em km²**.
3. Exportamos camadas leves (imagens georreferenciadas + GeoJSON + `stats.json`).
4. Um **app Flask** serve o mapa web com **slider antes/depois**, painel de números e avisos de limitação.

**Plano B (se as cenas de Moçambique não estiverem públicas):** cheia da Índia/Nepal de fim de setembro de 2026 (rios Gandak, Ganga, Kosi). Os dados de set/2026 estão dentro da carga pública "provisional". [CONFIRMADO que o evento existiu; cobertura NISAR da área é TERCEIROS]

---

## 6. Decisões técnicas e justificativas

| # | Decisão | Status | Justificativa |
|---|---|---|---|
| D1 | Caso de estudo: Moçambique, jan/2026 | **DECIDIDO** (14/11, equipe) | Maior impacto documentado + há referência oficial da NASA. |
| D2 | Plano B: Índia/Nepal, set/2026 | **DECIDIDO como fallback** | Dados provisional garantidamente públicos. |
| D3 | Cortar previsão de risco | **DECIDIDO** | Sem histórico NISAR; inviável em ~20h. |
| D4 | Backend/front: **Flask** + Leaflet (ou MapLibre) em templates simples | **DECIDIDO** (equipe prefere o que conversa melhor com Flask) | Menos peças, menos coisas que quebram. |
| D5 | Processamento **offline**; o app só mostra resultados pré-calculados | **PROPOSTO** | Máquinas com 8 GB de RAM; demo estável; sem processamento ao vivo. |
| D6 | Ler **apenas janelas** do HDF5 (nunca o arquivo inteiro na RAM) | **PROPOSTO** | Limite de 8 GB; arquivos NISAR são grandes (relato de ~2,6 GB para um GUNW). |
| D7 | Produto: **GCOV** (não GUNW) | **PROPOSTO** | É o mais simples para água/cheia; GUNW exige conhecimento de InSAR e tem armadilhas. |
| D8 | Detecção de água por **limiar em dB** (HH/HV) + filtro de speckle + máscara de água permanente | **PROPOSTO** | Clássico, explicável e defensável; sem rótulos de treino não há ML confiável. |
| D9 | **Sem treinar modelos de ML** | **PROPOSTO** | Sem rótulos, sem tempo, difícil validar. IA entra na **explicação**, não na detecção. |
| D10 | Processamento pesado: **GitHub Codespace** do Victor, previsto para ~14:30 de 14/11 | **DECIDIDO** (Victor garante) | Mas ver nota abaixo. |
| D11 | Hospedagem do app com link público | **PENDENTE** (Victor escolhe) | Precisa suportar Flask; o link não pode exigir login. |
| D12 | Licença do repositório | **PENDENTE** | Sugestão: Apache-2.0 (alinha com a distribuição padrão da NASA). |
| D13 | Vídeo: gravação real do app + intro/encerramento com IA 3D, editado pelo **Jhuan** | **PROPOSTO** | Judges avaliam o que funciona; IA só como complemento. Declarar uso de IA. |

**Nota sobre Codespace:** são máquinas separadas, **não somam processamento**. Uso recomendado: um Codespace maior, ou cada pessoa processa uma cena diferente e **comita só o resultado leve**. **Nunca** comitar arquivos HDF5 brutos nem credenciais. [HIPÓTESE sobre cotas: verificar o plano]

**Não esperar o Codespace:** o download e o recorte por janela podem rodar localmente em paralelo (a equipe tem espaço em disco). O Codespace é acelerador, não bloqueio.

---

## 7. Arquitetura e tecnologias

```
 NASA Earthdata / ASF DAAC
 (busca sem login; download com conta Earthdata)
            │
            ▼
 [ Pipeline offline em Python ]            roda no PC ou no Codespace
   asf_search / earthaccess  → download
   h5py + numpy + rasterio   → leitura por janela, dB, recorte
   (scipy / skimage)         → filtro de speckle, limiar, máscara
            │
            ▼
 outputs/   (versionados, leves)
   • overlays georreferenciados (PNG + limites) ou GeoTIFF/COG
   • flood_polygons.geojson
   • stats.json  (km² alagados, datas, trilha/frame, polarização)
            │
            ▼
 [ Flask ]  serve estático + /api/stats  (+ /api/route, na fase 2)
            │
            ▼
 [ Front ]  Leaflet/MapLibre · slider antes/depois · painel de números
            · avisos "dados provisórios" · explicação em linguagem simples
            │
            ▼
 Deploy público (link sem login)  →  link no formulário de submissão
```

**Bibliotecas candidatas** (nenhuma instalada/verificada neste ambiente de planejamento): `asf_search`, `earthaccess`, `h5py`, `numpy`, `rasterio`, `scipy`/`scikit-image`, `geopandas`, `shapely`, `flask`; fase 2: `osmnx` ou `networkx` para estradas/rotas.

**Acesso aos dados:**
- Busca: Earthdata Search, **ASF Vertex** (`search.asf.alaska.edu`), API `asf_search`, CMR. A **busca não exige login**; o **download exige conta Earthdata** (gratuita).
- Guia de dados: `nisar-docs.asf.alaska.edu`.
- Segredos (usuário/senha/token) **só em variáveis de ambiente / Codespaces secrets / `.netrc` fora do repositório**.

---

## 8. Funcionalidades planejadas

**Fase 1 — MVP (obrigatório, alvo: sáb 14/11 à noite)**
1. Mapa com a área de estudo e **slider antes / durante**.
2. Camada de **água detectada** pelo NISAR e **área alagada (km²)**.
3. Painel com datas, trilha/frame, polarização e **aviso "dados provisórios"**.
4. Página "Como ler o radar" (explicação curta: por que a água aparece escura, por que as nuvens não importam).
5. App no ar com **link público**.

**Fase 2 — Diferenciais (domingo, por prioridade)**
1. **Validação cruzada** com um produto de referência (candidatos a verificar: OPERA DSWx-S1/DSWx-HLS, mapas de emergência existentes de Moçambique). Mostrar precisão honesta.
2. **Vias e edificações** (OpenStreetMap) cruzadas com a água → **vias bloqueadas**.
3. **Rota segura simples** entre dois pontos evitando áreas alagadas (opcional).
4. Mais datas da série, se existirem cenas.
5. **Texto explicativo por IA** (resumo em linguagem simples, claramente rotulado como gerado por IA).
6. Tratamento de **floresta alagada** (HH/HV) como limitação ou extra: limiar simples pode errar aqui.

**Fase 3 — Entrega**
Vídeo de 30 s (ou 7 slides), textos da submissão em inglês, README, lista de referências, uso de IA declarado, envio final.

**Fora de escopo (decidido):** previsão de risco, treinamento de modelos, GUNW/deformação, processamento ao vivo, cobertura global.

---

## 9. Fontes de dados e referências

**Oficiais do desafio (lista colada pela equipe)** [CONFIRMADO]
- Earthdata Search — https://search.earthdata.nasa.gov/search
- ASF Vertex — https://search.asf.alaska.edu/
- NISAR Data User Guide — https://nisar-docs.asf.alaska.edu/
- Intro Remote Sensing — https://www.earthdata.nasa.gov/learn/earth-observation-data-basics/remote-sensing
- Intro SAR — https://www.earthdata.nasa.gov/learn/earth-observation-data-basics/sar
- ARSET (treinamentos, inclui NISAR) — https://appliedsciences.nasa.gov/get-involved/training
- NISAR StoryMaps (floods etc.) — https://nisar.jpl.nasa.gov/applications/arcgis-storymaps/
- NISAR White Papers — https://nisar.jpl.nasa.gov/applications/societal-benefit/
- Parceiras: CSA (RCM, tutorial SAR em Python), CONAE (SAOCOM).

**Pesquisa da sessão de planejamento**
- NASA SVS #5661 — *NISAR Reveals Major Flooding in Mozambique* (publicado 06/08/2026): https://svs.gsfc.nasa.gov/5661 [CONFIRMADO]. Dados: NISAR GCOV, 5 e 17/01/2026.
- Liberação pública NISAR L-band (20/07/2026), observações a partir de 17/06/2026, via ASF DAAC. [CONFIRMADO — Earthdata]
  https://www.earthdata.nasa.gov/news/nisar-l-band-data-released-expanding-record-surface-changes
- Níveis de maturidade: **BETA** (liberações de jan/fev 2026) e **PROVISIONAL** (jul/2026 em diante). Dados antigos "serão liberados nos próximos meses". [CONFIRMADO]
- Produção provisional pausada 23/10–06/11/2026, retomada após 06/11. [CONFIRMADO — Earthdata]
  https://www.earthdata.nasa.gov/data/alerts-outages/nisar-provisional-data-production-paused-oct.-23-nov.-6-2026
- Lacuna permanente de dados 27/07–10/08/2026 (não afeta janeiro). [CONFIRMADO]
- Produtos úteis (nomes de coleção no CMR, segundo catálogo de terceiros): `NISAR_L2_GCOV_PROVISIONAL_V1`, `NISAR_L2_GUNW_PROVISIONAL_V1`; referências `OPERA_L2_RTC-S1_V1`, `OPERA_L3_DSWX-HLS_V1`. [TERCEIROS] **A coleção BETA que contém janeiro de 2026 precisa ser identificada.** [A VERIFICAR]
- Guias de submissão e julgamento: https://www.spaceappschallenge.org/resources/project-submission-guide/ e https://www.spaceappschallenge.org/resources/judging-awards-guide
- Contexto de cheia (Índia/Nepal, set/2026): https://www.aljazeera.com/news/2026/09/27/floods-and-landslides-kill-at-least-56-people-in-india-12-in-nepal [CONFIRMADO]

**Projetos semelhantes (apenas para posicionamento; não copiar código):** SARabande, EchoSphere, MOTUS, TerraCascade, Nova Matrics VI, disasterWatch, OpenSource-SAR e um projeto de inundação sob vegetação (L-band vs C-band) da Índia (DWTS). Padrão comum: mapa Leaflet + slider antes/depois. Várias usam dados ópticos ou simulados no lugar de NISAR real. **Nosso diferencial deve ser NISAR real + validação + camada operacional.**

---

## 10. Restrições e riscos

| Risco | Impacto | Mitigação |
|---|---|---|
| Cenas de jan/2026 sobre Moçambique **não estão públicas** | Projeto inteiro | Verificar hoje no ASF Vertex/Earthdata Search; se falhar, **Plano B** (Índia/Nepal). |
| Só 2 datas disponíveis (5 e 17/01) | Pouca série temporal | Aceitar: foco em antes/durante; storytelling forte. |
| 8 GB de RAM | Travamentos | Leitura por janela; processar por partes; Codespace como apoio. |
| Dados **provisórios** (sujeitos a reprocessamento) | Credibilidade | Rotular em todo lugar; não vender como produto validado. |
| Limiar simples **erra floresta alagada** e água rugosa/vento | Validade | Documentar como limitação; usar HH/HV; validar contra referência. |
| Falta de pessoa de design/narrativa | Apresentação | Jhuan edita o vídeo; Flau lidera o roteiro; começar o storyboard cedo. |
| Prazo / fuso errado | Perda total | Confirmar Local Event hoje; **enviar até 21:00 de domingo**. |
| Link do vídeo/projeto privado | Inelegibilidade | Testar em janela anônima antes de enviar. |
| Declaração de IA esquecida | Desclassificação | Manter `AI_USAGE_LOG.md` desde já. |
| Deploy cair | Demo quebrada | Fallback: site estático com as camadas pré-geradas + vídeo gravado. |

---

## 11. Equipe e papéis

| Pessoa | Principal | Secundário | Foco neste projeto |
|---|---|---|---|
| **Victor** | Back-end | Front-end | Repositório, Codespace, Flask, integração, deploy, submissão. |
| **Davi** | Back-end | IA | Pipeline de dados (download, recorte, export), OSM/rotas, textos da submissão. |
| **Flau** | IA | Front-end | Método de detecção de água, validação, UI do slider, texto por IA, vídeo/roteiro. |

Apoio externo: **Jhuan** (editor de vídeo, não integrante da equipe Space Apps; **não pode constar como membro sem registro**; citar como colaborador se aplicável).
Equipe trabalha em **turnos** (inclui noite). Quem passa o turno atualiza a seção 13.

---

## 12. Estado atual do desenvolvimento

- **Código (14/11 ~12:00):** estrutura do repo criada (`app/`, `pipeline/`, `outputs/`, `docs/`, `data/`). Existe um **esqueleto Flask** (`app/app.py`) com mapa Leaflet, slider antes/durante e painel, rodando sobre **dados MOCK** (`outputs/mock/`). **O mapa Leaflet nunca foi aberto no navegador** (rede do ambiente de desenvolvimento bloqueou o CDN); só o servidor e a sintaxe do JS foram testados. Contrato do `stats.json` em `docs/stats_contract.md`. O pipeline de dados **ainda não existe**. O script `nisar_recon.py` não está no repo.
- **Contas Earthdata:** [A VERIFICAR] se os três já criaram.
- **Registro no Space Apps / Local Event:** [A VERIFICAR] se os três estão no mesmo evento e qual o fuso.
- **Dados:** a busca no ASF Vertex (Davi, T03) achou **10 cenas** sobre a área (lista em `TASKS.xlsx`, aba "Cenas NISAR"). **Par válido para o MVP [CONFIRMADO pelos nomes dos arquivos]:** dois GCOV, ciclo 009 (05/01/2026) e ciclo 010 (17/01/2026), ambos trilha **114**, direção **A (ascendente)**, frame **165**. Nada baixado ainda. **[A VERIFICAR]** coleção (BETA?), polarizações (o código "DHDH" do nome sugere dual-pol, é suposição) e estrutura do HDF5. Os nomes sugerem também uma aquisição em 24/12/2025 (ciclo 008), que pode servir como data "antes" (T38).
- **Codespace:** Victor prevê funcionando por volta de 14:30 de 14/11; é a primeira tarefa dele no turno.

---

## 13. Decisões, pendências e próximos passos

**Decisões tomadas**
- Caso Moçambique (A), plano B Índia/Nepal. Previsão de risco cortada. Flask. Começar simples e evoluir em fases. Trabalho em turnos.

**Turnos (suposição de 14/11, ajustar se mudar)**
- **1 · Flau (sozinho):** agora até ~15:30 de sáb. Conta, confirmar GO, baixar os 2 GCOV, inspecionar o HDF5, começar o recorte em dB.
- **2 · Victor:** ~15:30 até ~23:30 de sáb. **Primeira tarefa: Codespace.** Depois hospedagem, Flask, interface, integração, deploy. Flau continua no pipeline (recorte, água, exportação).
- **3 · Davi:** ~23:30 de sáb até ~08:00 de dom. Aceitação do MVP, fallback, OSM, validação.
- **Dom:** todos. Meta de envio 21:00; prazo duro 23:59 (fuso a confirmar).
- Detalhes por tarefa em `TASKS.xlsx`. Quem passa o turno atualiza este arquivo (seções 12, 13, 15).

**Decisão proposta (aguarda OK de Victor e Davi):** **GO em Moçambique**, usando os dois GCOV de 05/01 e 17/01/2026 (trilha 114, direção A, frame 165). Licença sugerida: Apache-2.0 (ainda sem arquivo LICENSE, aguardando OK).

**Pendências (preencher e mover para "tomadas")**
1. Os 3 criarem conta Earthdata e confirmarem registro no mesmo Local Event + fuso do prazo.
2. **Go/no-go de dados:** existem ≥2 cenas NISAR GCOV (mesma trilha/direção, HH/HV) sobre Limpopo/Incomati em janeiro/2026? Qual coleção (BETA ou provisional)?
3. Escolha de hospedagem pública (D11) e licença (D12).
4. Referência de validação (qual produto, para qual data).
5. Fonte de estradas/edificações (OSM) e limite da área de estudo.
6. Nome do projeto/tagline (inglês, curto).
7. Responsável final pelo vídeo e combinação com o Jhuan.

**Próximos passos imediatos**
1. Contas Earthdata → busca de cenas (bbox aproximado: oeste 32.0, sul -26.0, leste 33.5, norte -24.0; datas 01–20/01/2026) → decisão go/no-go até ~12:00.
2. Criar repositório e esqueleto Flask com mapa e dados de exemplo.
3. Baixar cenas e extrair HH/HV recortadas.

---

## 14. Instruções para agentes de IA que usarem este arquivo

1. **Não invente dados, datas, números ou citações.** Se algo não está aqui nem em fonte oficial, diga que não sabe.
2. **Diferencie** confirmado / terceiros / hipótese / a verificar, como neste documento.
3. **Rotule sempre** os dados NISAR como **provisórios** (ou BETA, conforme a coleção).
4. **Nunca** coloque credenciais, tokens ou arquivos HDF5 brutos no repositório.
5. **Não use logos ou marcas da NASA.** Imagens/vídeo/áudio/código gerados por IA devem ser registrados em `AI_USAGE_LOG.md`.
6. **Priorize o que roda.** Não proponha funcionalidades que ameacem o MVP. Se algo for opcional, diga.
7. **Não tome decisões importantes sozinho:** registre como "PROPOSTO" e peça confirmação humana.
8. Escreva textos de submissão e do app em **inglês**; este arquivo e a comunicação interna ficam em português.
9. Ao terminar uma tarefa, **atualize a seção 12/13 e o log abaixo.**

---

## 15. Log de mudanças

| Data/hora | Quem | Mudança |
|---|---|---|
| 14/11/2026 ~10:00 | Planejamento (Claude + equipe) | Versão 0.1: pesquisa do evento e do desafio, caso Moçambique escolhido, escopo cortado, arquitetura proposta. |
| 14/11/2026 ~12:00 | Flau (com Claude) | Versão 0.2: 10 cenas encontradas (par GCOV 05/01 e 17/01, trilha 114, A, frame 165), GO proposto, turnos registrados, estrutura do repo, esqueleto Flask com dados mock e contrato do `stats.json`. |
