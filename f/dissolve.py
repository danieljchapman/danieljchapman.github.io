import geopandas as gpd, pandas as pd, zipfile, sys
O=sys.argv[1]
z=zipfile.ZipFile('f/baf/cd2025.zip'); n=[x for x in z.namelist() if x.endswith('.xlsx')][0]
baf=pd.read_excel(z.open(n), dtype=str)
print(baf.columns.tolist(), len(baf)); print(baf.head())
geo=[c for c in baf.columns if 'GEO' in c.upper() or 'BLOCK' in c.upper()][0]; dist=[c for c in baf.columns if c!=geo][0]
blk=gpd.read_file('zip://'+O+'/tl_2020_39_tabblock20.zip')
blk=blk.merge(baf[[geo,dist]].rename(columns={geo:'GEOID20',dist:'DISTRICT'}),on='GEOID20',how='left')
print('unassigned',blk.DISTRICT.isna().sum(), 'pop',blk.loc[blk.DISTRICT.isna(),'POP20'].astype(int).sum() if 'POP20' in blk else '')
blk=blk[blk.DISTRICT.notna()]
pop=blk.groupby('DISTRICT')['POP20'].sum() if 'POP20' in blk else None; print(pop)
d=blk[['DISTRICT','geometry']].dissolve(by='DISTRICT').reset_index()
d['geometry']=d.geometry.buffer(0)
d.to_crs(4326).to_file(O+'/oh_cd2025.geojson',driver='GeoJSON')
print(d)
