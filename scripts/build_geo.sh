#!/bin/sh
# Rebuild the detailed map layers from Natural Earth 1:10m (public domain) — only needed when updating them.
#   download into a folder: ne_10m_land, ne_10m_lakes, ne_10m_rivers_lake_centerlines, ne_10m_admin_0_countries
#   (https://naciscdn.org/naturalearth/10m/{physical,cultural}/<name>.zip), then: npm run geo -- <folder>
set -e
NE="${1:?usage: npm run geo -- <folder with the Natural Earth zips>}"
OUT=static/vendor/geo
for z in ne_10m_land ne_10m_admin_0_countries ne_10m_lakes ne_10m_rivers_lake_centerlines; do unzip -o -q "$NE/$z.zip" "$z.*" -d "$NE"; done

# coastlines, borders, lakes and rivers for zoomed-in views
npx mapshaper -i "$NE/ne_10m_land.shp" "$NE/ne_10m_admin_0_countries.shp" "$NE/ne_10m_lakes.shp" "$NE/ne_10m_rivers_lake_centerlines.shp" combine-files \
  -rename-layers land,countries,lakes,rivers \
  -innerlines target=countries + name=borders \
  -filter 'scalerank <= 6' target=lakes \
  -filter 'scalerank <= 7 && featurecla == "River"' target=rivers \
  -filter-fields target=land,lakes,rivers,borders '' \
  -clip bbox=-180,-85,180,85 target=land,lakes,rivers,borders \
  -simplify 22% keep-shapes target=land,lakes,rivers,borders \
  -o "$OUT/detail-10m.json" format=topojson quantization=60000 target=land,borders,lakes,rivers

# Russian country names at their label points, with the zoom they appear at
npx mapshaper -i "$NE/ne_10m_admin_0_countries.shp" \
  -filter 'NAME_RU != ""' \
  -points x=LABEL_X y=LABEL_Y \
  -each 'name = NAME_RU, min = MIN_LABEL' \
  -filter-fields name,min \
  -o "$OUT/labels.json" format=geojson precision=0.01
ls -la "$OUT"
