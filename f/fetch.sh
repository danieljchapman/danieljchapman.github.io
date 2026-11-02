#!/bin/bash
# round 7: more Crane A1 file-name guesses (the media server ignores the extension)
O=f/out7; mkdir -p $O; cd $O
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
B=https://www.michigan.gov/micrc/-/media/Project/Websites/MiCRC/405CraneA1
for s in Shape_File Shape_Files ShapeFiles Shapefiles Shapefile Shape_file Shape_files SHAPEFILE SHAPEFILES Shp_Files Shapefile_Zip Shapefiles_Zip GeoJSON Geojson KML KMZ Kmz Plan Block_Equivalency BlockEquivalency BEF Assignment Assignments Block_Assignment_File BAF_File Data_Files Files GIS_Files Map_Files Shape Shapes Partisan_Fairness PartisanFairness Core_Retention CoreRetention Legal_Description; do
  c=$(curl -s -A "$UA" -m 30 -o /tmp/x -w '%{http_code}' "$B/405_CraneA1_$s.zip"); if [ "$c" = 200 ]; then cp /tmp/x "405_CraneA1_$s.bin"; echo "HIT $s $(file -b /tmp/x | cut -c1-40)" >> log.txt; fi
done
for s in 405_CraneA1 405CraneA1 CraneA1 Crane_A1; do c=$(curl -s -A "$UA" -m 30 -o /tmp/x -w '%{http_code}' "$B/$s.zip"); [ "$c" = 200 ] && { cp /tmp/x "$s.bin"; echo "HIT $s" >> log.txt; }; done
get(){ curl -sSL -A "$UA" -m 200 -o "$1" -w "$1 %{http_code} %{size_download}\n" "${@:2}" >> log.txt 2>>err.txt; }
get report.html https://www.michigan.gov/micrc/reports/commission-report-2024
echo done >> log.txt; ls -la > ls.txt
