#!/usr/bin/env python3
"""Projects NC county and congressional-plan shapefiles to SVG paths (same format as the Texas files).

Usage: python3 build_shapes.py SHAPE_DIR OUT_DIR
Sources: county boundaries from NCSBE (ShapeFiles/CountyBoundary/NC_State_County_Boundary_NCGS_2017.zip);
congressional plans from the General Assembly (ncleg.gov/Files/GIS/Plans_Main) and NCSBE (2025 plan).
Projection: NC State Plane (EPSG:32119), scaled to a W x H viewBox shared by every map.
"""
import json, os, sys, glob
import shapefile
from pyproj import CRS, Transformer
from shapely.geometry import shape, mapping
from shapely.ops import transform, unary_union
import warnings; warnings.filterwarnings('ignore', category=DeprecationWarning)

W = 900
# output file -> (plan folders under SHAPE_DIR, simplification relative to the county map)
# Legislative districts are drawn finer because city districts are small and get zoomed in on.
PLANS = {'nc_ushouse_district_shapes.json': (['c2016', 'c2019', 'c2022', 'c2023', 'c2025'], 1),
         'nc_house_district_shapes.json': (['h2011', 'h2018', 'h2019', 'h2022', 'h2023'], 0.4),
         'nc_senate_district_shapes.json': (['s2011', 's2018', 's2019', 's2022', 's2023'], 0.5)}
TARGET = CRS.from_epsg(32119)
# [name, lat, lon, tier] for map labels: tier 1 always shown, tier 2 from 2x zoom, tier 3 from 4x
CITIES = [['Charlotte', 35.2271, -80.8431, 1], ['Raleigh', 35.7796, -78.6382, 1], ['Greensboro', 36.0726, -79.792, 1], ['Durham', 35.994, -78.8986, 1],
          ['Winston-Salem', 36.0999, -80.2442, 2], ['Fayetteville', 35.0527, -78.8784, 1], ['Wilmington', 34.2257, -77.9447, 1], ['Asheville', 35.5951, -82.5515, 1],
          ['Greenville', 35.6127, -77.3664, 1], ['Cary', 35.7915, -78.7811, 3], ['High Point', 35.9557, -80.0053, 2], ['Concord', 35.4088, -80.5795, 2],
          ['Gastonia', 35.2621, -81.1873, 2], ['Jacksonville', 34.7541, -77.4302, 2], ['Chapel Hill', 35.9132, -79.0558, 2], ['Rocky Mount', 35.9382, -77.7905, 2],
          ['Burlington', 36.0957, -79.4378, 2], ['Wilson', 35.7212, -77.9156, 2], ['Hickory', 35.7332, -81.3412, 2], ['Goldsboro', 35.3849, -77.9928, 2],
          ['Boone', 36.2168, -81.6746, 2], ['New Bern', 35.1085, -77.0441, 2], ['Elizabeth City', 36.2946, -76.2511, 2], ['Huntersville', 35.4107, -80.8429, 3],
          ['Apex', 35.7327, -78.8503, 3], ['Mooresville', 35.5849, -80.8101, 3], ['Wake Forest', 35.9799, -78.5097, 3], ['Sanford', 35.4799, -79.1803, 3],
          ['Salisbury', 35.6709, -80.4742, 3], ['Monroe', 34.9854, -80.5495, 3], ['Statesville', 35.7826, -80.8873, 3], ['Lumberton', 34.6182, -79.0086, 3],
          ['Kinston', 35.2627, -77.5816, 3], ['Morganton', 35.7454, -81.6848, 3], ['Hendersonville', 35.3187, -82.461, 3], ['Shelby', 35.2924, -81.5356, 3],
          ['Kill Devil Hills', 36.0307, -75.676, 3], ['Morehead City', 34.7229, -76.726, 3], ['Southern Pines', 35.174, -79.3923, 3], ['Roanoke Rapids', 36.4615, -77.6541, 3],
          ['Murphy', 35.0876, -84.0352, 3], ['Lexington', 35.8240, -80.2534, 3], ['Albemarle', 35.3501, -80.2001, 3]]


def load(path):
    prj = open(path[:-4] + '.prj').read()
    tr = Transformer.from_crs(CRS.from_wkt(prj), TARGET, always_xy=True)
    r = shapefile.Reader(path)
    fields = [f[0] for f in r.fields[1:]]
    for sr in r.iterShapeRecords():
        geom = shape(sr.shape.__geo_interface__)
        if not geom.is_valid:
            geom = geom.buffer(0)
        yield dict(zip(fields, sr.record)), transform(tr.transform, geom)


def path_of(geom, fit, tol):
    geom = geom.simplify(tol, preserve_topology=True)
    out = []
    polys = geom.geoms if geom.geom_type == 'MultiPolygon' else [geom]
    for p in polys:
        if p.area < (tol * 4) ** 2:
            continue
        for ring in [p.exterior] + list(p.interiors):
            pts = [fit(x, y) for x, y in ring.coords]
            out.append('M' + 'L'.join(f'{x:.1f},{y:.1f}' for x, y in pts[:-1]) + 'Z')
    return ''.join(out)


def main(src, out):
    counties = list(load(glob.glob(os.path.join(src, 'counties', '*.shp'))[0]))
    # The county boundary file runs out into the sounds and the ocean; clip everything to the land outline from
    # the Census cartographic counties (us-atlas counties-10m), widened 1.5 km so state lines stay intact.
    gj = json.load(open(os.path.join(src, 'nc_counties_carto.geojson')))
    ll = Transformer.from_crs(CRS.from_epsg(4326), TARGET, always_xy=True)
    land = unary_union([transform(ll.transform, shape(f['geometry'])).buffer(0) for f in gj['features']]).buffer(1500)
    counties = [(rec, g.intersection(land)) for rec, g in counties]
    state = unary_union([g for _, g in counties])
    x0, y0, x1, y1 = state.bounds
    pad = 6
    k = (W - 2 * pad) / (x1 - x0)
    H = round((y1 - y0) * k + 2 * pad)
    fit = lambda x, y: (pad + (x - x0) * k, pad + (y1 - y) * k)
    tol = 0.6 / k   # about 0.6 px
    fips, by = {}, {}
    for rec, g in counties:
        n = str(rec['County']).strip()
        fips[n.upper()] = f"37{int(rec['FIPS']):03d}"
        by.setdefault(n, []).append(g)
    assert fips == json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'nc_county_fips.json')))
    cty = [{'county_fips': fips[n.upper()], 'county': 'McDowell' if n.upper() == 'MCDOWELL' else n.title(), 'path': path_of(unary_union(gs), fit, tol)} for n, gs in sorted(by.items())]
    json.dump(cty, open(os.path.join(out, 'nc_county_shapes.json'), 'w'), separators=(',', ':'))
    for fname, (plans, rel) in PLANS.items():
        dist = []
        for plan in plans:
            shp = glob.glob(os.path.join(src, plan, '**', '*.shp'), recursive=True)[0]
            rows = list(load(shp))
            key = next(f for f in rows[0][0] if f.upper() == 'DISTRICT')
            print(plan, len(rows))
            for rec, g in rows:
                dist.append({'plan': plan, 'district': int(rec[key]), 'path': path_of(g.intersection(land), fit, tol * rel)})
        json.dump(dist, open(os.path.join(out, fname), 'w'), separators=(',', ':'))
    cities = [[n, *[round(v, 1) for v in fit(*ll.transform(lo, la))], t] for n, la, lo, t in CITIES]
    json.dump({'width': W, 'height': H, 'cities': cities}, open(os.path.join(out, 'nc_map_size.json'), 'w'))
    print('viewBox', W, H)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
