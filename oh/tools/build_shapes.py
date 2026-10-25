#!/usr/bin/env python3
"""Projects Ohio county and district boundaries to SVG paths (same format as the Texas, NC and GA files).

Usage: python3 build_shapes.py SHAPE_DIR OUT_DIR
Sources in SHAPE_DIR (U.S. Census Bureau cartographic boundary files, 500k, clipped to the shoreline):
  cb_2020_us_county_500k.zip
  cb_2018_us_cd116_500k.zip / cb_2022_us_cd118_500k.zip   congressional districts used in 2016-2020 / 2022-2024
  oh_cd2025.geojson   the Oct. 31, 2025 congressional plan (2026), dissolved from the Ohio Redistricting Commission's
                      block assignment file and 2020 Census blocks; clipped here to the state's shoreline
  cb_2018/2022/2024_39_sldl_500k.zip, ..._sldu_...  Ohio House / Senate districts used in 2016-2020 / 2022 / 2024-2026
"""
import json, os, sys
import geopandas as gpd
from shapely.ops import unary_union

W = 600
CRS = '+proj=tmerc +lat_0=40.2 +lon_0=-82.7 +k=1 +x_0=0 +y_0=0 +datum=NAD83 +units=m'
PLANS = {'oh_ushouse_district_shapes.json': ([('c2012', 'cb_2018_us_cd116_500k.zip', 'CD116FP'), ('c2022', 'cb_2022_us_cd118_500k.zip', 'CD118FP'),
                                              ('c2025', 'oh_cd2025.geojson', 'DISTRICT')], 1),
         'oh_house_district_shapes.json': ([('h2012', 'cb_2018_39_sldl_500k.zip', 'SLDLST'), ('h2022', 'cb_2022_39_sldl_500k.zip', 'SLDLST'),
                                            ('h2023', 'cb_2024_39_sldl_500k.zip', 'SLDLST')], 0.4),
         'oh_senate_district_shapes.json': ([('s2012', 'cb_2018_39_sldu_500k.zip', 'SLDUST'), ('s2022', 'cb_2022_39_sldu_500k.zip', 'SLDUST'),
                                             ('s2023', 'cb_2024_39_sldu_500k.zip', 'SLDUST')], 0.5)}
# [name, lat, lon, tier]: tier 1 always shown, tier 2 from 2x zoom, tier 3 from 4x
CITIES = [['Columbus', 39.9612, -82.9988, 1], ['Cleveland', 41.4993, -81.6944, 1], ['Cincinnati', 39.1031, -84.5120, 1], ['Toledo', 41.6528, -83.5379, 1],
          ['Akron', 41.0814, -81.5190, 1], ['Dayton', 39.7589, -84.1916, 1], ['Youngstown', 41.0998, -80.6495, 1],
          ['Canton', 40.7989, -81.3784, 2], ['Lorain', 41.4529, -82.1824, 2], ['Springfield', 39.9242, -83.8088, 2], ['Mansfield', 40.7584, -82.5154, 2],
          ['Lima', 40.7426, -84.1052, 2], ['Zanesville', 39.9403, -82.0132, 2], ['Athens', 39.3292, -82.1013, 2], ['Sandusky', 41.4489, -82.7080, 2],
          ['Portsmouth', 38.7318, -82.9977, 2], ['Steubenville', 40.3698, -80.6340, 2], ['Findlay', 41.0442, -83.6499, 2], ['Marietta', 39.4154, -81.4548, 2],
          ['Chillicothe', 39.3331, -82.9824, 2], ['Wooster', 40.8051, -81.9351, 2],
          ['Hamilton', 39.3995, -84.5613, 3], ['Middletown', 39.5151, -84.3983, 3], ['Parma', 41.4048, -81.7229, 3], ['Elyria', 41.3684, -82.1076, 3],
          ['Kettering', 39.6895, -84.1688, 3], ['Mason', 39.3601, -84.3099, 3], ['Dublin', 40.0992, -83.1141, 3], ['Westerville', 40.1262, -82.9291, 3],
          ['Delaware', 40.2987, -83.0680, 3], ['Newark', 40.0581, -82.4013, 3], ['Lancaster', 39.7137, -82.5993, 3], ['Medina', 41.1384, -81.8637, 3],
          ['Mentor', 41.6662, -81.3396, 3], ['Kent', 41.1537, -81.3579, 3], ['Bowling Green', 41.3748, -83.6513, 3], ['Marion', 40.5887, -83.1285, 3]]


def main(src, out):
    cty = gpd.read_file('zip://' + os.path.join(src, 'cb_2020_us_county_500k.zip'))
    cty = cty[cty.STATEFP == '39'].to_crs(CRS)
    assert len(cty) == 88
    state = unary_union(list(cty.geometry))
    x0, y0, x1, y1 = state.bounds
    pad = 6
    k = (W - 2 * pad) / (x1 - x0)
    H = round((y1 - y0) * k + 2 * pad)
    fit = lambda x, y: (pad + (x - x0) * k, pad + (y1 - y) * k)
    tol = 0.5 / k

    def path_of(geom, t):
        geom = geom.simplify(t, preserve_topology=True)
        polys = geom.geoms if geom.geom_type == 'MultiPolygon' else [geom] if geom.geom_type == 'Polygon' else [g for g in getattr(geom, 'geoms', []) if g.geom_type == 'Polygon']
        o = []
        for p in polys:
            if p.area < (t * 4) ** 2:
                continue
            for ring in [p.exterior] + list(p.interiors):
                pts = [fit(x, y) for x, y in ring.coords]
                o.append('M' + 'L'.join(f'{x:.1f},{y:.1f}' for x, y in pts[:-1]) + 'Z')
        return ''.join(o)

    rows = [{'county_fips': r.GEOID, 'county': r.NAME, 'path': path_of(r.geometry, tol)} for r in cty.sort_values('NAME').itertuples()]
    json.dump(rows, open(os.path.join(out, 'oh_county_shapes.json'), 'w'), separators=(',', ':'))
    for fname, (plans, rel) in PLANS.items():
        dist = []
        for plan, f, field in plans:
            p = os.path.join(src, f)
            g = gpd.read_file(p if f.endswith('.geojson') else 'zip://' + p)
            if 'STATEFP' in g.columns:
                g = g[g.STATEFP == '39']
            g = g.to_crs(CRS)
            n = 0
            for r in g.itertuples():
                v = str(getattr(r, field)).strip()
                if not v.isdigit():
                    continue  # 'ZZZ' water areas
                geom = r.geometry.buffer(0).intersection(state) if f.endswith('.geojson') else r.geometry
                dist.append({'plan': plan, 'district': int(v), 'path': path_of(geom, tol * rel)}); n += 1
            print(plan, n)
        json.dump(dist, open(os.path.join(out, fname), 'w'), separators=(',', ':'))
    import pyproj
    ll = pyproj.Transformer.from_crs('EPSG:4326', CRS, always_xy=True)
    cities = [[n, *[round(v, 1) for v in fit(*ll.transform(lo, la))], t] for n, la, lo, t in CITIES]
    json.dump({'width': W, 'height': H, 'cities': cities}, open(os.path.join(out, 'oh_map_size.json'), 'w'))
    print('viewBox', W, H)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
