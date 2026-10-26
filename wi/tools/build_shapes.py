#!/usr/bin/env python3
"""Projects Wisconsin county and district boundaries to SVG paths (same format as the Texas, NC and GA files).

Usage: python3 build_shapes.py SHAPE_DIR OUT_DIR
Sources in SHAPE_DIR (U.S. Census Bureau cartographic boundary files, 500k, clipped to the shoreline):
  cb_2020_us_county_500k.zip
  cb_2018/2022/2024_55_sldl_500k.zip   State Assembly districts: 2011 plan (2016-2020), April 2022 plan (2022), 2024 plan (2024-2026)
  cb_2018/2022/2024_55_sldu_500k.zip   State Senate districts, same plans
"""
import json, os, sys
import geopandas as gpd
from shapely.ops import unary_union

W = 600
CRS = '+proj=tmerc +lat_0=44.7 +lon_0=-89.8 +k=1 +x_0=0 +y_0=0 +datum=NAD83 +units=m'
PLANS = {'wi_house_district_shapes.json': ([('a2011', 'cb_2018_55_sldl_500k.zip', 'SLDLST'), ('a2022', 'cb_2022_55_sldl_500k.zip', 'SLDLST'),
                                            ('a2024', 'cb_2024_55_sldl_500k.zip', 'SLDLST')], 0.4),
         'wi_senate_district_shapes.json': ([('s2011', 'cb_2018_55_sldu_500k.zip', 'SLDUST'), ('s2022', 'cb_2022_55_sldu_500k.zip', 'SLDUST'),
                                             ('s2024', 'cb_2024_55_sldu_500k.zip', 'SLDUST')], 0.5)}
# [name, lat, lon, tier]: tier 1 always shown, tier 2 from 2x zoom, tier 3 from 4x
CITIES = [['Milwaukee', 43.0389, -87.9065, 1], ['Madison', 43.0731, -89.4012, 1], ['Green Bay', 44.5133, -88.0133, 1], ['Eau Claire', 44.8113, -91.4985, 1],
          ['La Crosse', 43.8014, -91.2396, 1], ['Wausau', 44.9591, -89.6301, 1], ['Superior', 46.7208, -92.1041, 1], ['Appleton', 44.2619, -88.4154, 1],
          ['Kenosha', 42.5847, -87.8212, 2], ['Racine', 42.7261, -87.7829, 2], ['Waukesha', 43.0117, -88.2315, 2], ['Oshkosh', 44.0247, -88.5426, 2],
          ['Janesville', 42.6828, -89.0187, 2], ['Sheboygan', 43.7508, -87.7145, 2], ['Fond du Lac', 43.7730, -88.4470, 2], ['Stevens Point', 44.5236, -89.5746, 2],
          ['Manitowoc', 44.0886, -87.6576, 2], ['Rhinelander', 45.6366, -89.4121, 2], ['Ashland', 46.5924, -90.8838, 2], ['Hudson', 44.9747, -92.7568, 2],
          ['Platteville', 42.7342, -90.4785, 2], ['Marshfield', 44.6689, -90.1718, 2], ['Beloit', 42.5083, -89.0318, 2], ['West Bend', 43.4253, -88.1834, 2],
          ['Brookfield', 43.0606, -88.1065, 3], ['West Allis', 43.0167, -88.0070, 3], ['Menomonee Falls', 43.1789, -88.1173, 3], ['Sun Prairie', 43.1836, -89.2137, 3],
          ['Fitchburg', 42.9608, -89.4698, 3], ['Middleton', 43.0972, -89.5043, 3], ['De Pere', 44.4489, -88.0604, 3], ['Neenah', 44.1858, -88.4626, 3],
          ['Watertown', 43.1947, -88.7290, 3], ['Mequon', 43.2158, -87.9845, 3], ['Menomonie', 44.8755, -91.9193, 3], ['Chippewa Falls', 44.9369, -91.3929, 3],
          ['Baraboo', 43.4711, -89.7443, 3], ['Whitewater', 42.8336, -88.7323, 3], ['Wisconsin Rapids', 44.3836, -89.8174, 3]]


def main(src, out):
    cty = gpd.read_file('zip://' + os.path.join(src, 'cb_2020_us_county_500k.zip'))
    cty = cty[cty.STATEFP == '55'].to_crs(CRS)
    assert len(cty) == 72
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
    json.dump(rows, open(os.path.join(out, 'wi_county_shapes.json'), 'w'), separators=(',', ':'))
    for fname, (plans, rel) in PLANS.items():
        dist = []
        for plan, f, field in plans:
            p = os.path.join(src, f)
            g = gpd.read_file(p if f.endswith('.geojson') else 'zip://' + p)
            if 'STATEFP' in g.columns:
                g = g[g.STATEFP == '55']
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
    json.dump({'width': W, 'height': H, 'cities': cities}, open(os.path.join(out, 'wi_map_size.json'), 'w'))
    print('viewBox', W, H)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
