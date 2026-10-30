O=f/out3; mkdir -p $O
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
get(){ n=$1; shift; for u in "$@"; do code=$(curl -sSL -A "$UA" -m 400 -o "$O/$n" -w "%{http_code}" "$u" 2>>$O/err.txt); echo "$n $code $(stat -c%s $O/$n 2>/dev/null) $u" >> $O/log.txt; if [ "$code" = 200 ] && head -c 5 $O/$n | grep -q '%PDF'; then return; fi; sleep 3; done; }
get c2016.pdf "https://apps.azsos.gov/election/2016/General/Official%20Signed%20State%20Canvass.pdf" "https://web.archive.org/web/20161220192915id_/http://apps.azsos.gov/election/2016/General/Official%20Signed%20State%20Canvass.pdf"
get c2018.pdf "https://apps.azsos.gov/election/2018/2018_1203_signed_official_statewide_canvass.pdf" "https://azsos.gov/sites/default/files/2018%201203%20Signed%20Official%20Statewide%20Canvass.pdf" "https://web.archive.org/web/20181207054635id_/https://azsos.gov/sites/default/files/2018%201203%20Signed%20Official%20Statewide%20Canvass.pdf"
get c2020.pdf "https://apps.azsos.gov/election/2020/2020_general_state_canvass.pdf" "https://web.archive.org/web/20201130193108id_/https://azsos.gov/sites/default/files/2020_General_State_Canvass.pdf"
get c2022.pdf "http://apps.azsos.gov/election/2022/General/canvass/2022dec05_general_election_canvass_web.pdf" "https://web.archive.org/web/20221205195258id_/https://azsos.gov/sites/default/files/2022Dec05_General_Election_Canvass_Web.pdf"
get c2022recount.pdf "https://azsos.gov/sites/default/files/2022_GE_Statewide_Recount_Results_for_Website.pdf" "https://web.archive.org/web/20221229234553id_/https://azsos.gov/sites/default/files/2022_GE_Statewide_Recount_Results_for_Website.pdf"
get c2024.pdf "http://apps.azsos.gov/election/2024/ge/canvass/20241105_GeneralCanvass_Signed.pdf"
get c2026primary_page.html "https://azsos.gov/elections/election-information/2026-election-info"
