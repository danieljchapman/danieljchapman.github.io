import { geoAlbersUsa } from 'd3-geo';
import fs from 'fs';
const p = geoAlbersUsa().scale(1300).translate([487.5, 305]);
const rows = fs.readFileSync(process.argv[2], 'utf8').split('\n').slice(1).filter(Boolean).map((l) => l.split('\t').map((x) => x.trim()));
const out = {};
for (const r of rows) {
  const st = r[0], g = r[1];
  if (!/^\d{4}$/.test(g) || st === 'DC' || st === 'PR' || g.endsWith('98')) continue;
  const xy = p([Number(r[7]), Number(r[6])]);
  out[`${st}-${g.slice(2)}`] = xy;
}
fs.writeFileSync(process.argv[3], JSON.stringify(out));
console.log(Object.keys(out).length, Object.values(out).filter((v) => !v).length);
