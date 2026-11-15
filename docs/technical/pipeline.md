# Pipeline de dados

O pipeline é executado offline; a aplicação web consome os artefatos
resultantes. Os HDF5 originais e os intermediários de processamento ficam em
`data/` e não são versionados.

## Preparar o ambiente

```bash
python -m pip install -r requirements.txt -r requirements-pipeline.txt
```

O download NISAR usa autenticação Earthdata. Guarde o token como variável de
ambiente `EARTHDATA_TOKEN`; não inclua credenciais no Git.

## Fluxo principal

1. Baixar cenas GCOV, se elas ainda não estiverem em `data/`:

   ```bash
   python pipeline/download_gcov.py
   ```

   O script usa os dois granules configurados no código. Consulte o
   [guia de download](../download.md) para token Earthdata e alternativa manual.

2. Recortar, fazer multilook e converter HH/HV para dB para cada cena:

   ```bash
   python pipeline/make_db.py --file data/SCENE_20260105.h5 --tag 20260105
   python pipeline/make_db.py --file data/SCENE_20260117.h5 --tag 20260117
   ```

   Substitua `SCENE_...` pelo nome real do arquivo baixado.

3. Detectar água e gerar overlays/máscaras:

   ```bash
   python pipeline/detect_flood.py --loosen 3
   ```

4. Comparar a máscara com EMSR857 AOI02. O padrão espera a máscara
   `outputs/flood_extent.geojson` (gerada pelo detector) e o pacote
   `data/reference/EMSR857_products.zip`. Atualiza `outputs/stats.json` e
   `outputs/validation_difference.geojson`:

   ```bash
   python pipeline/validate_reference.py
   ```

5. Preparar a rede viária para o planejador:

   ```bash
   python pipeline/prepare_network.py --download
   ```

6. Para regenerar resumo e GeoJSON de impacto OSM:

   ```bash
   python pipeline/osm_impact.py
   ```

7. Reconstruir a cópia estática depois de alterar o app ou os artefatos:

   ```bash
   python pipeline/build_static.py
   ```

## Saídas importantes

| Artefato | Origem / consumidor |
|---|---|
| `outputs/stats.json` | Contrato de dados usado por Flask e frontend. |
| `outputs/water_before.png`, `water_during.png` | Overlays de água pré-gerados. |
| `outputs/flood_new_water.tif` | Máscara de água nova usada na análise e rotas. |
| `outputs/validation_difference.geojson` | Áreas exclusivas NISAR e EMS dentro do recorte comparado. |
| `outputs/impact_features.geojson`, `impact_roads.geojson` | Feições e vias OSM cruzadas com a estimativa de inundação. |
| `outputs/routing_network.npz` | Rede compilada carregada pelo servidor para o motor de rotas. |
| `docs/` | HTML, JavaScript, dados e overlays usados pelo GitHub Pages. |

## Reprodutibilidade e proveniência

- Guarde as cenas e produtos de terceiros junto dos metadados de origem
  localmente; não suponha que arquivos ignorados pelo Git estarão no clone.
- Confira `mock: false` antes de publicar uma saída analítica. O construtor
  estático recusa explicitamente estatísticas marcadas como mock.
- Não misture resultados de datas diferentes sem atualizar os metadados e
  registrar a janela temporal.
- Registre alterações de método e de dados no `stats.json`, neste manual e no
  log de uso de IA quando aplicável.
