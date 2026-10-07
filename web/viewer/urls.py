"""앱의 URL. 서브패스 접두사는 여기가 모른다 — `gsmweb/urls.py` 가 붙인다."""
from django.urls import path, re_path

from . import views

app_name = "viewer"

urlpatterns = [
    path("", views.intro_view, name="intro"),
    path("map/", views.map_view, name="map"),
    path("manage/", views.manage_view, name="manage"),
    path("manage/login/", views.manage_login, name="manage-login"),
    path("manage/logout/", views.manage_logout, name="manage-logout"),
    path("manage/sources/<slug:source_id>/", views.source_edit, name="source-edit"),
    path("linked/fetch/", views.linked_fetch, name="linked-fetch"),
    path("healthz/", views.healthz, name="healthz"),
    path("3d/", views.map3d_view, name="map3d"),
    path("moon/", views.moon_view, name="moon"),
    re_path(r"^moon/tiles/(?P<layer>[a-z-]+)/(?P<z>\d{1,2})/(?P<x>\d{1,5})/(?P<y>\d{1,5})\.png$",
            views.moon_tile, name="moon-tile"),
    # 달 극 평면 — 극 평사도법 격자 (052)
    re_path(r"^moon/ptiles/(?P<pole>[ns])/(?P<layer>[a-z-]+)/(?P<z>\d{1,2})/(?P<x>\d{1,5})/(?P<y>\d{1,5})\.png$",
            views.moon_polar_tile, name="moon-polar-tile"),
    re_path(r"^moon/dem/(?P<z>\d{1,2})/(?P<x>\d{1,5})/(?P<y>\d{1,5})\.png$", views.moon_dem, name="moon-dem"),
    path("moon/info/", views.moon_info, name="moon-info"),
    path("moon/profile/", views.moon_profile, name="moon-profile"),
    path("elevation/profile/", views.elevation_profile, name="elevation-profile"),
    path("profile/band/", views.profile_band, name="profile-band"),
    path("moon/values/", views.moon_values, name="moon-values"),
    path("mars/values/", views.mars_values_at, name="mars-values"),
    path("mercury/values/", views.mercury_values_at, name="mercury-values"),
    path("moon/legend/", views.moon_legend, name="moon-legend"),
    path("moon/places/", views.moon_places, name="moon-places"),
    path("moon/landings/", views.moon_landings, name="moon-landings"),
    path("moon/eva/", views.moon_eva, name="moon-eva"),
    # NASA Trek 의 MapServer 판 — 달·화성·수성이 함께 쓴다 (060, 수성은 wetherilli 185)
    re_path(r"^trek/(?P<body>moon|mars|mercury)/map/(?P<label>[\w.-]+)/(?P<z>\d{1,2})/(?P<x>\d{1,5})/(?P<y>\d{1,5})\.png$",
            views.trek_map_tile, name="trek-map-tile"),
    re_path(r"^trek/(?P<body>moon|mars)/map/(?P<label>[\w.-]+)/p/(?P<pole>[ns])/(?P<z>\d{1,2})/(?P<x>\d{1,5})/(?P<y>\d{1,5})\.png$",
            views.trek_map_polar_tile, name="trek-map-polar-tile"),
    re_path(r"^trek/(?P<body>moon|mars|mercury)/map/(?P<label>[\w.-]+)/info/$", views.trek_map_info, name="trek-map-info"),
    re_path(r"^trek/(?P<body>moon|mars|mercury)/map/(?P<label>[\w.-]+)/legend/$", views.trek_map_legend,
            name="trek-map-legend"),
    path("mars/", views.mars_view, name="mars"),
    re_path(r"^mars/tiles/(?P<layer>[a-z-]+)/(?P<z>\d{1,2})/(?P<x>\d{1,5})/(?P<y>\d{1,5})\.png$",
            views.mars_tile, name="mars-tile"),
    # 화성 극 평면 — 극 평사도법 격자 (065)
    re_path(r"^mars/ptiles/(?P<pole>[ns])/(?P<layer>[a-z-]+)/(?P<z>\d{1,2})/(?P<x>\d{1,5})/(?P<y>\d{1,5})\.png$",
            views.mars_polar_tile, name="mars-polar-tile"),
    re_path(r"^mars/dem/(?P<z>\d{1,2})/(?P<x>\d{1,5})/(?P<y>\d{1,5})\.png$", views.mars_dem, name="mars-dem"),
    path("mars/info/", views.mars_info, name="mars-info"),
    path("mars/legend/", views.mars_legend, name="mars-legend"),
    path("mars/places/", views.mars_places, name="mars-places"),
    path("mars/profile/", views.mars_profile, name="mars-profile"),
    path("mercury/", views.mercury_view, name="mercury"),
    re_path(r"^mercury/dem/(?P<z>\d{1,2})/(?P<x>\d{1,5})/(?P<y>\d{1,5})\.png$", views.mercury_dem,
            name="mercury-dem"),
    re_path(r"^mercury/tiles/(?P<layer>[a-z-]+)/(?P<z>\d{1,2})/(?P<x>\d{1,5})/(?P<y>\d{1,5})\.png$",
            views.mercury_tile, name="mercury-tile"),
    path("mercury/info/", views.mercury_info, name="mercury-info"),
    path("mercury/legend/", views.mercury_legend, name="mercury-legend"),
    path("mercury/places/", views.mercury_places, name="mercury-places"),
    path("mercury/profile/", views.mercury_profile, name="mercury-profile"),
    path("earth/", views.earth_view, name="earth"),
    re_path(r"^earth/tiles/geology/(?P<z>\d{1,2})/(?P<x>\d{1,6})/(?P<y>\d{1,6})\.png$", views.earth_tile,
            name="earth-tile"),
    path("earth/info/", views.earth_info, name="earth-info"),
    path("earth/legend/", views.earth_legend, name="earth-legend"),
    path("earth/paleo/", views.earth_paleo, name="earth-paleo"),
    re_path(r"^earth/paleo/tiles/(?P<style>land|edge|coast)/(?P<age>\d{1,4})/(?P<z>\d{1,2})/(?P<x>\d{1,4})/(?P<y>\d{1,4})\.png$",
            views.earth_paleo_tile, name="earth-paleo-tile"),
    path("earth/paleo/at/", views.earth_paleo_at, name="earth-paleo-at"),
    re_path(r"^earth/fossils/tiles/(?P<ka>\d{1,7})/(?P<z>\d{1,2})/(?P<x>\d{1,4})/(?P<y>\d{1,4})\.png$",
            views.earth_fossil_tile, name="earth-fossil-tile"),
    path("earth/fossils/at/", views.earth_fossil_at, name="earth-fossil-at"),
    # 화석 산지 밀도 열지도 (fossils.py, wetherilli 286)
    re_path(r"^earth/fossils/density/(?P<ka>\d{1,7})/(?P<z>\d{1,2})/(?P<x>\d{1,4})/(?P<y>\d{1,4})\.png$",
            views.earth_fossil_density_tile, name="earth-fossil-density-tile"),
    re_path(r"^earth/volcanoes/tiles/(?P<z>\d{1,2})/(?P<x>\d{1,4})/(?P<y>\d{1,4})\.png$", views.earth_volcano_tile,
            name="earth-volcano-tile"),
    re_path(r"^earth/volcanoes/pleistocene/tiles/(?P<z>\d{1,2})/(?P<x>\d{1,4})/(?P<y>\d{1,4})\.png$", views.earth_volcano_tile,
            {"kind": "pleistocene"}, name="earth-pleistocene-tile"),
    path("earth/volcanoes/at/", views.earth_volcano_at, name="earth-volcano-at"),
    re_path(r"^earth/quakes/tiles/(?P<band>quake\d{1,2})/(?P<z>\d{1,2})/(?P<x>\d{1,4})/(?P<y>\d{1,4})\.png$",
            views.earth_quake_tile, name="earth-quake-tile"),
    path("earth/quakes/at/", views.earth_quake_at, name="earth-quake-at"),
    # 최근 지진 — USGS 실시간 피드 (wetherilli 292)
    re_path(r"^earth/recentquakes/tiles/(?P<z>\d{1,2})/(?P<x>\d{1,4})/(?P<y>\d{1,4})\.png$", views.earth_recent_quake_tile,
            name="earth-recent-quake-tile"),
    path("earth/recentquakes/at/", views.earth_recent_quake_at, name="earth-recent-quake-at"),
    re_path(r"^earth/neotoma/tiles/(?P<band>neo_[a-z]{1,6})/(?P<ka>\d{1,4})/(?P<z>\d{1,2})/(?P<x>\d{1,4})/(?P<y>\d{1,4})\.png$",
            views.earth_neotoma_tile, name="earth-neotoma-tile"),
    path("earth/neotoma/at/", views.earth_neotoma_at, name="earth-neotoma-at"),
    re_path(r"^earth/crust/tiles/(?P<z>\d{1,2})/(?P<x>\d{1,4})/(?P<y>\d{1,4})\.png$", views.earth_crust_tile,
            name="earth-crust-tile"),
    path("earth/crust/at/", views.earth_crust_at, name="earth-crust-at"),
    # 세계 빙하 RGI 7.0 (glaciers.py, wetherilli 289)
    re_path(r"^earth/glaciers/tiles/(?P<z>\d{1,2})/(?P<x>\d{1,4})/(?P<y>\d{1,4})\.png$", views.earth_glaciers_tile, name="earth-glaciers-tile"),
    path("earth/glaciers/at/", views.earth_glaciers_at, name="earth-glaciers-at"),
    # 충돌구·거대 화성암 지대 (impacts.py, wetherilli 283)
    re_path(r"^earth/impacts/(?P<layer>impacts|lips)/(?P<ma>\d{1,4})/(?P<z>\d{1,2})/(?P<x>\d{1,4})/(?P<y>\d{1,4})\.png$",
            views.earth_impacts_tile, name="earth-impacts-tile"),
    path("earth/impacts/at/", views.earth_impacts_at, name="earth-impacts-at"),
    # 세계 활성단층 GEM (faults.py, wetherilli 279)
    re_path(r"^earth/faults/tiles/(?P<z>\d{1,2})/(?P<x>\d{1,4})/(?P<y>\d{1,4})\.png$", views.earth_faults_tile, name="earth-faults-tile"),
    path("earth/faults/at/", views.earth_faults_at, name="earth-faults-at"),
    # 세계 광상 USGS — 광종 칸마다 (minerals.py, wetherilli 276)
    re_path(r"^earth/minerals/tiles/(?P<band>min_[a-z]+)/(?P<z>\d{1,2})/(?P<x>\d{1,4})/(?P<y>\d{1,4})\.png$",
            views.earth_minerals_tile, name="earth-minerals-tile"),
    path("earth/minerals/at/", views.earth_minerals_at, name="earth-minerals-at"),
    # 지각 응력 World Stress Map 2025 (stress.py, wetherilli 273)
    re_path(r"^earth/stress/tiles/(?P<z>\d{1,2})/(?P<x>\d{1,4})/(?P<y>\d{1,4})\.png$", views.earth_stress_tile, name="earth-stress-tile"),
    path("earth/stress/at/", views.earth_stress_at, name="earth-stress-at"),
    # 판 경계·세계 지질구 (tectonics.py, wetherilli 272)
    re_path(r"^earth/tectonics/(?P<layer>tbound|tprov)/(?P<z>\d{1,2})/(?P<x>\d{1,4})/(?P<y>\d{1,4})\.png$",
            views.earth_tectonics_tile, name="earth-tectonics-tile"),
    path("earth/tectonics/at/", views.earth_tectonics_at, name="earth-tectonics-at"),
    # 세계 암상 GLiM·지열류 IHFC (glim.py·heatflow.py, wetherilli 267)
    re_path(r"^earth/glim/tiles/(?P<z>\d{1,2})/(?P<x>\d{1,4})/(?P<y>\d{1,4})\.png$", views.earth_glim_tile, name="earth-glim-tile"),
    path("earth/glim/at/", views.earth_glim_at, name="earth-glim-at"),
    re_path(r"^earth/heatflow/tiles/(?P<z>\d{1,2})/(?P<x>\d{1,4})/(?P<y>\d{1,4})\.png$", views.earth_heatflow_tile,
            name="earth-heatflow-tile"),
    path("earth/heatflow/at/", views.earth_heatflow_at, name="earth-heatflow-at"),
    # 해양 지각 연대·퇴적층 두께 (seafloor.py, wetherilli 264)
    re_path(r"^earth/seafloor/(?P<layer>seaage|sediment)/(?P<z>\d{1,2})/(?P<x>\d{1,4})/(?P<y>\d{1,4})\.png$",
            views.earth_seafloor_tile, name="earth-seafloor-tile"),
    path("earth/seafloor/at/", views.earth_seafloor_at, name="earth-seafloor-at"),
    re_path(r"^earth/ne/tiles/(?P<style>water|ice)/(?P<z>\d{1,2})/(?P<x>\d{1,4})/(?P<y>\d{1,4})\.png$",
            views.earth_ne_tile, name="earth-ne-tile"),
    re_path(r"^earth/icemargins/tiles/(?P<ka>\d{1,4})/(?P<z>\d{1,2})/(?P<x>\d{1,4})/(?P<y>\d{1,4})\.png$",
            views.earth_icemargin_tile, name="earth-icemargin-tile"),
    re_path(r"^earth/mantle/(?P<frame>\d{1,2})/(?P<layer>slabs|piles|boundaries)\.bin$", views.earth_mantle,
            name="earth-mantle"),
    path("earth/places/", views.earth_places, name="earth-places"),
    # 바람 — 구워 둔 u·v 텍스처 (koprifossillab P02)
    path("earth/wind/", views.earth_wind_index, name="earth-wind"),
    path("earth/ocean/", views.earth_ocean_index, name="earth-ocean"),
    re_path(r"^earth/ocean/(?P<source>ecco2)/(?P<stamp>\d{8})/surface\.png$", views.earth_ocean_png, name="earth-ocean-png"),
    re_path(r"^earth/wind/(?P<source>gfs|era5|gmgsi)/(?P<stamp>\d{8}|\d{10})/(?P<level>10m|250hPa|cloud-(?:total|low|mid|high)|sat)\.png$", views.earth_wind_png,
            name="earth-wind-png"),
    path("earth/labels/", views.earth_labels, name="earth-labels"),
    path("pointsets/<int:pk>/paleo/", views.earth_paleo_set, name="pointset-paleo"),
    path("mars/landings/", views.mars_landings, name="mars-landings"),
    path("mars/traverses/", views.mars_traverses, name="mars-traverses"),

    # 상류 프록시. 브라우저는 인증키를 모르고 이 둘만 부른다.
    path("wms/", views.wms, name="wms"),
    path("featureinfo/", views.feature_info, name="featureinfo"),

    path("legend/", views.legend, name="legend"),
    # 벡터 레이어(단층)의 모양. 1° 칸 하나씩 (devlog 020)
    path("vector/", views.vector, name="vector"),
    # 점 레이어(그린란드 정부 포털). 타일이 아니라 GeoJSON 한 덩이다 (devlog 019)
    path("points/", views.point_layer, name="points"),

    # 남극 지질도 — 우리가 그리는 EPSG:3031 타일 (geomap.py). `@2x` 는 512 px
    re_path(r"^geomap/(?P<layer>[\w-]+)/(?P<z>\d{1,2})/(?P<x>\d{1,7})/(?P<y>\d{1,7})(?P<retina>@2x)?\.png$",
            views.geomap_tile, name="geomap-tile"),

    # 일본 지질도 — GSJ 심리스 지질도 타일·속성·범례 (gsj.py, devlog 024). 레이어는 `gsj:` 를 뗀 이름
    re_path(r"^gsj/(?P<layer>[\w-]+)/(?P<z>\d{1,2})/(?P<x>\d{1,5})/(?P<y>\d{1,5})\.png$",
            views.gsj_tile, name="gsj-tile"),
    # 한반도 지질도 음영판 — 우리가 잘라 둔 EPSG:5179 타일 (peninsula.py, devlog 027)
    re_path(r"^peninsula/(?P<layer>[\w-]+)/(?P<z>\d{1,2})/(?P<x>\d{1,4})/(?P<y>\d{1,4})\.webp$",
            views.peninsula_tile, name="peninsula-tile"),
    # 남극 해저·빙저 지형 IBCSO v2 — 우리가 잘라 둔 EPSG:3031 타일 (ibcso.py, devlog 047)
    re_path(r"^ibcso/(?P<layer>bed|ice)/(?P<z>\d{1,2})/(?P<x>\d{1,3})/(?P<y>\d{1,3})\.webp$",
            views.ibcso_tile, name="ibcso-tile"),
    # 남극 자력 이상 ADMAP-2 — 우리가 칠해 잘라 둔 3031 타일과 누른 자리의 nT (admap.py, wetherilli 262)
    re_path(r"^admap/(?P<z>\d{1,2})/(?P<x>\d{1,3})/(?P<y>\d{1,3})\.webp$", views.admap_tile, name="admap-tile"),
    path("admap/info/", views.admap_info, name="admap-info"),
    # IBCSO 자료 출처(TID) 타일과 속성, 누른 자리의 수심·표고 (ibcso.py, devlog 070·071)
    re_path(r"^ibcso/tid/(?P<z>\d{1,2})/(?P<x>\d{1,3})/(?P<y>\d{1,3})\.png$",
            views.ibcso_tid_tile, name="ibcso-tid-tile"),
    path("ibcso/info/", views.ibcso_info, name="ibcso-info"),
    path("ibcso/depth/", views.ibcso_depth, name="ibcso-depth"),
    # 3D 가 쓰는 것 — 평면 격자(5179·5181·3031) 타일을 3857 로 다시 편다 (warp.py, 040)
    re_path(r"^warp/(?P<upstream>peninsula|phyloserver|geomap|ibcso|admap)/(?P<layer>[\w-]+)/(?P<z>\d{1,2})/(?P<x>\d{1,6})/(?P<y>\d{1,6})(?P<retina>@2x)?\.png$",
            views.warp_tile, name="warp-tile"),
    # 한반도 지질도 — phyloserver 의 카카오 격자 타일 (phyloserver.py, devlog 026)
    re_path(r"^phyloserver/(?P<layer>[\w-]+)/(?P<level>\d{1,2})/(?P<x>\d{1,5})_(?P<y>\d{1,5})\.png$",
            views.phyloserver_tile, name="phyloserver-tile"),
    # VWorld 배경지도 — 브라우저가 곧장 못 받을 때만 거친다 (사내 VPN, devlog 033)
    re_path(r"^vworld/(?P<layer>\w+)/(?P<z>\d{1,2})/(?P<y>\d{1,7})/(?P<x>\d{1,7})\.(?:png|jpeg)$",
            views.vworld_tile, name="vworld-tile"),
    # 조건이 열린 배경 — 서버가 받아 담는다 (basemaps.py, wetherilli 184)
    re_path(r"^gibs/(?P<epsg>4326|3413|3031)/(?P<layer>\w+)/(?P<z>\d{1,2})/(?P<y>\d{1,5})/(?P<x>\d{1,5})\.jpeg$",
            views.gibs_tile, name="gibs-tile"),
    path("gibs/wms/", views.gibs_wms, name="gibs-wms"),
    # NPI 스발바르 배경 타일 — 서버가 담는다 (basemaps.py, wetherilli 200)
    re_path(r"^npi/(?P<service>NP_\w+)/(?P<z>\d{1,2})/(?P<y>\d{1,6})/(?P<x>\d{1,6})$", views.npi_tile, name="npi-tile"),
    path("gebco/wms/", views.gebco_wms, name="gebco-wms"),
    # 브라질 — 보는 범위의 범례 (sgb.py, wetherilli 191)
    path("sgb/legend/", views.sgb_legend, name="sgb-legend"),
    # 페루 — REST 타일 캐시 중계·누른 자리·보는 범위의 범례 (ingemmet.py, wetherilli 195), 단층·습곡은 export 를 타일 칸으로 (222)
    re_path(r"^ingemmet/(?P<sheet>50k|50k_units|100k|faults_1m|faults_100k|folds_100k|faults_50k|folds_50k|occ_metal|occ_nonmetal|deposits|projects|belts|bouguer|aeromag|rmi|lithium|gq_[a-z]{2})/(?P<z>\d{1,2})/(?P<x>\d{1,6})/(?P<y>\d{1,6})\.png$",
            views.ingemmet_tile, name="ingemmet-tile"),
    path("ingemmet/info/", views.ingemmet_info, name="ingemmet-info"),
    # 대앤틸리스 — 우리가 구운 USGS SIM 3534 (caribmap.py, wetherilli 254)
    re_path(r"^sim3534/(?P<sheet>units|faults)/(?P<z>\d{1,2})/(?P<x>\d{1,6})/(?P<y>\d{1,6})\.png$",
            views.sim3534_tile, name="sim3534-tile"),
    path("sim3534/info/", views.sim3534_info, name="sim3534-info"),
    path("sim3534/legend/", views.sim3534_legend, name="sim3534-legend"),
    path("ingemmet/legend/", views.ingemmet_legend, name="ingemmet-legend"),
    # 우루과이 — REST 범례를 목록으로 (dinamige.py, wetherilli 196)
    path("dinamige/legend/", views.dinamige_legend, name="dinamige-legend"),
    # 몽골 — REST 범례를 목록으로, 시대는 층서 지수에서 푼다 (mris.py, wetherilli 221)
    path("mris/legend/", views.mris_legend, name="mris-legend"),
    # 사우디 — 보는 범위의 범례 (sgs.py, wetherilli 227)
    path("sgs/legend/", views.sgs_legend, name="sgs-legend"),
    path("sigeom/legend/", views.sigeom_legend, name="sigeom-legend"),
    path("esdm/legend/", views.esdm_legend, name="esdm-legend"),
    path("mrdata/legend/", views.mrdata_legend, name="mrdata-legend"),
    path("units/legend/", views.units_legend, name="units-legend"),
    path("gns/legend/", views.gns_legend, name="gns-legend"),
    # 동남아 — ArcGIS REST 범례를 목록으로, 문 여럿이 함께 (jmg.py·dmr.py, wetherilli 228)
    path("list/legend/", views.list_legend, name="list-legend"),
    # 남아공 — REST 범례를 목록으로 (cgs.py, wetherilli 209)
    path("cgs/legend/", views.cgs_legend, name="cgs-legend"),
    # 에콰도르 — 보는 범위의 범례 (iige.py, wetherilli 198)
    path("iige/legend/", views.iige_legend, name="iige-legend"),
    # 멕시코 — 보는 범위의 범례 (sgm.py, wetherilli 206)
    path("sgm/legend/", views.sgm_legend, name="sgm-legend"),
    # 호주 — 보는 범위의 범례 (ga.py, wetherilli 212)
    path("ga/legend/", views.ga_legend, name="ga-legend"),
    path("austates/legend/", views.austates_legend, name="austates-legend"),
    path("gsj/info/", views.gsj_info, name="gsj-info"),
    path("gsj/legend/", views.gsj_legend, name="gsj-legend"),
    # 지질도Navi 판 목록 (wetherilli 171) — 일본 탭이 판 목록을 펼 때 받는다
    path("gsj/geonavi/", views.gsj_geonavi, name="gsj-geonavi"),
    path("gsmma/legend/", views.gsmma_legend, name="gsmma-legend"),
    # 5만 지질도의 층리·엽리·절리 자리 — 커서와 팝업 (jikhanjung 004)
    path("kigam50k/attitudes/", views.kigam50k_attitudes, name="kigam50k-attitudes"),
    path("kigam50k/rose/", views.kigam50k_rose, name="kigam50k-rose"),

    path("catalog/", views.catalog_json, name="catalog"),
    path("patchnotes/", views.patch_notes, name="patchnotes"),

    path("pointsets/", views.pointset_index, name="pointset-index"),
    path("pointsets/upload/", views.pointset_upload, name="pointset-upload"),
    path("pointsets/create/", views.pointset_create, name="pointset-create"),
    # 주소만 적힌 CSV — 화면이 주소를 나눠 보내 좌표를 받는다 (wetherilli 152)
    path("pointsets/geocode/", views.pointset_geocode, name="pointset-geocode"),
    path("pointsets/<int:pk>/geojson/", views.pointset_geojson, name="pointset-geojson"),
    path("pointsets/<int:pk>/csv/", views.pointset_csv, name="pointset-csv"),
    path("pointsets/deleted/", views.pointset_deleted, name="pointset-deleted"),
    path("pointsets/deleted/<int:pk>/restore/", views.pointset_restore, name="pointset-restore"),
    path("pointsets/<int:pk>/delete/", views.pointset_delete, name="pointset-delete"),
    path("pointsets/<int:pk>/elevation/", views.pointset_elevation, name="pointset-elevation"),
    path("pointsets/<int:pk>/places/", views.pointset_places, name="pointset-places"),
    # 3D 의 촘촘한 지형 — 극지 PGC·일본 국토지리원을 Terrarium 꼴로 (elevation.py, 031·032)
    re_path(r"^dem/(?P<z>\d{1,2})/(?P<x>\d{1,6})/(?P<y>\d{1,6})\.png$", views.dem_tile, name="dem-tile"),
    # 얼음을 걷어 낸 남극 — IBCSO 해저·빙저 (051)
    re_path(r"^dem/(?P<kind>bed)/(?P<z>\d{1,2})/(?P<x>\d{1,6})/(?P<y>\d{1,6})\.png$", views.dem_tile,
            name="dem-bed-tile"),

    path("coords/parse/", views.coord_parse, name="coord-parse"),
    path("coords/project/", views.coord_project, name="coord-project"),
    path("search/", views.place_search, name="place-search"),
    # 스발바르 지명 찾기 (NPI, devlog 021) — 한국의 search/ 자리
    path("placenames/", views.place_names, name="place-names"),
    path("whereis/", views.whereis, name="whereis"),
]
