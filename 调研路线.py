import os
import re
import json
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image
import folium
from folium.plugins import Fullscreen


# ============================================================
# 0. 基本配置
# ============================================================

TRIP_DIR = Path(r"路线")
PHOTO_DIR = TRIP_DIR / "files"
OUTPUT_HTML = TRIP_DIR / "index.html"

# ============================================================
# CARTO API KEY
# ============================================================

CARTO_API_KEY = "cb1_31qo_1_dc98e69ddf266a7b9d0a8530"

BASEMAP_SOURCE = (
    f"https://basemaps.cartocdn.com/light_all/"
    "{z}/{x}/{y}.png"
    f"?key={CARTO_API_KEY}"
)


# ============================================================
# 1. 路段定义
# ============================================================

SEGMENTS = [
    {
        "name": "晋绫北路",
        "photos": (
            list(range(1, 14))
            + list(range(26, 47))
            + list(range(170, 175))
        ),
    },
    {
        "name": "北塘河（南）",
        "photos": list(range(14, 26)),
    },
    {
        "name": "庐山路（新北中心公园）",
        "photos": list(range(47, 55)),
    },
    {
        "name": "珠江路",
        "photos": list(range(55, 93)),
    },
    {
        "name": "龙业路（恐龙园）",
        "photos": list(range(93, 102)),
    },
    {
        "name": "河海东路",
        "photos": list(range(102, 110)),
    },
    {
        "name": "龙沧路",
        "photos": list(range(110, 128)),
    },
    {
        "name": "北塘河（北）&创意产业园区",
        "photos": list(range(128, 169)),
    },
]


# ============================================================
# 2. 检查文件夹
# ============================================================

if not TRIP_DIR.exists():
    raise FileNotFoundError(
        f"找不到路线文件夹：{TRIP_DIR}"
    )

if not PHOTO_DIR.exists():
    raise FileNotFoundError(
        f"找不到图片文件夹：{PHOTO_DIR}\n"
        f"请确认目录结构是：路线/files/"
    )


# ============================================================
# 3. 查找 KML
# ============================================================

kml_files = list(TRIP_DIR.glob("*.kml"))

if not kml_files:
    kml_files = list(TRIP_DIR.rglob("*.kml"))

if not kml_files:
    raise FileNotFoundError(
        "没有找到 KML 文件，请把 KML 放到“路线”文件夹中。"
    )

KML_FILE = kml_files[0]

print("=" * 70)
print("KML 文件：", KML_FILE)
print("=" * 70)


# ============================================================
# 4. 读取 KML
# ============================================================

tree = ET.parse(KML_FILE)
root = tree.getroot()

NS = {
    "kml": "http://www.opengis.net/kml/2.2",
    "gx": "http://www.google.com/kml/ext/2.2",
}


# ============================================================
# 5. 提取轨迹
# ============================================================

coordinates = []


# ------------------------------------------------------------
# 普通 LineString
# ------------------------------------------------------------

for elem in root.findall(
    ".//kml:LineString/kml:coordinates",
    NS
):
    if not elem.text:
        continue

    for point in elem.text.strip().split():

        values = point.split(",")

        if len(values) < 2:
            continue

        try:
            lon = float(values[0])
            lat = float(values[1])

            coordinates.append(
                [lat, lon]
            )

        except ValueError:
            pass


# ------------------------------------------------------------
# 如果没有 LineString，尝试 gx:Track
# ------------------------------------------------------------

if not coordinates:

    for elem in root.findall(
        ".//gx:Track/gx:coord",
        NS
    ):

        if not elem.text:
            continue

        values = elem.text.strip().split()

        if len(values) < 2:
            continue

        try:
            lon = float(values[0])
            lat = float(values[1])

            coordinates.append(
                [lat, lon]
            )

        except ValueError:
            pass


# ------------------------------------------------------------
# 最后 fallback
# ------------------------------------------------------------

if not coordinates:

    for elem in root.findall(
        ".//kml:coordinates",
        NS
    ):

        if not elem.text:
            continue

        for point in elem.text.strip().split():

            values = point.split(",")

            if len(values) < 2:
                continue

            try:
                lon = float(values[0])
                lat = float(values[1])

                coordinates.append(
                    [lat, lon]
                )

            except ValueError:
                pass


if not coordinates:
    raise ValueError(
        "KML 中没有读取到轨迹坐标。"
    )


print(
    "轨迹点数量：",
    len(coordinates)
)


# ============================================================
# 6. 轨迹中心
# ============================================================

center_lat = (
    sum(p[0] for p in coordinates)
    / len(coordinates)
)

center_lon = (
    sum(p[1] for p in coordinates)
    / len(coordinates)
)


# ============================================================
# 7. 获取照片 GPS
# ============================================================

def get_gps(image_path):

    try:

        image = Image.open(image_path)

        exif = image.getexif()

        if not exif:
            return None

        gps = exif.get_ifd(34853)

        if not gps:
            return None


        def rational_to_float(value):

            try:

                if hasattr(value, "numerator"):
                    return (
                        float(value.numerator)
                        / float(value.denominator)
                    )

                if isinstance(value, tuple):
                    return (
                        float(value[0])
                        / float(value[1])
                    )

                return float(value)

            except Exception:

                return float(value)


        lat = (
            rational_to_float(gps[2][0])
            + rational_to_float(gps[2][1]) / 60
            + rational_to_float(gps[2][2]) / 3600
        )

        lon = (
            rational_to_float(gps[4][0])
            + rational_to_float(gps[4][1]) / 60
            + rational_to_float(gps[4][2]) / 3600
        )


        if gps.get(1) in ["S", "s"]:
            lat = -lat

        if gps.get(3) in ["W", "w"]:
            lon = -lon


        return [
            lat,
            lon
        ]

    except Exception:

        return None


# ============================================================
# 8. 自然排序
# ============================================================

def natural_sort_key(path):

    parts = re.split(
        r"(\d+)",
        path.name
    )

    return [
        int(part)
        if part.isdigit()
        else part.lower()
        for part in parts
    ]


# ============================================================
# 9. 查找 files 文件夹中的图片
# ============================================================

IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp"
}


photo_files = []

for file in PHOTO_DIR.rglob("*"):

    if (
        file.is_file()
        and file.suffix.lower()
        in IMAGE_EXTENSIONS
    ):

        photo_files.append(file)


photo_files.sort(
    key=natural_sort_key
)


print(
    "找到照片：",
    len(photo_files)
)


if not photo_files:

    raise FileNotFoundError(
        f"在 {PHOTO_DIR} 中没有找到图片。"
    )


# ============================================================
# 10. 建立照片数据
# ============================================================

photos = []


for index, file in enumerate(
    photo_files,
    start=1
):

    gps = get_gps(file)

    # 浏览器使用的相对路径
    relative_path = file.relative_to(
        TRIP_DIR
    ).as_posix()

    photos.append(
        {
            "number": index,
            "name": file.name,
            "src": relative_path,
            "gps": gps,
        }
    )


gps_count = sum(
    1
    for p in photos
    if p["gps"] is not None
)


print(
    "具有 GPS 的照片：",
    gps_count
)


# ============================================================
# 11. 照片字典
# ============================================================

photo_dict = {
    p["number"]: p
    for p in photos
}


# ============================================================
# 12. 计算照片对应的最近轨迹点
# ============================================================

def nearest_route_point(lat, lon):

    best_point = None
    best_distance = float("inf")

    for point in coordinates:

        d = (
            (point[0] - lat) ** 2
            + (point[1] - lon) ** 2
        )

        if d < best_distance:

            best_distance = d
            best_point = point

    return best_point


for photo in photos:

    if photo["gps"] is None:

        photo["route_gps"] = None

        continue

    lat, lon = photo["gps"]

    nearest = nearest_route_point(
        lat,
        lon
    )

    photo["route_gps"] = nearest


# ============================================================
# 13. 创建 Folium 地图
# ============================================================

m = folium.Map(
    location=[
        center_lat,
        center_lon
    ],
    zoom_start=14,
    tiles=None,
    control_scale=True,
    prefer_canvas=True
)


# ============================================================
# 14. CARTO Light
# ============================================================

folium.TileLayer(
    tiles=BASEMAP_SOURCE,
    attr=(
        "© CARTO © OpenStreetMap contributors"
    ),
    name="CARTO Light",
    overlay=False,
    control=True,
    max_zoom=20,
).add_to(m)


# ============================================================
# 15. 主轨迹
# ============================================================

folium.PolyLine(
    coordinates,
    color="#222222",
    weight=4,
    opacity=0.85,
    smooth_factor=1,
    tooltip="完整轨迹"
).add_to(m)


# ============================================================
# 16. 起点
# ============================================================

folium.CircleMarker(
    coordinates[0],
    radius=7,
    color="#222222",
    fill=True,
    fill_color="#222222",
    fill_opacity=1,
    tooltip="起点"
).add_to(m)


# ============================================================
# 17. 终点
# ============================================================

folium.CircleMarker(
    coordinates[-1],
    radius=7,
    color="#222222",
    fill=True,
    fill_color="#222222",
    fill_opacity=1,
    tooltip="终点"
).add_to(m)


# ============================================================
# 18. 照片 Marker
# ============================================================

marker_names = {}


for photo in photos:

    if photo["gps"] is None:
        continue

    number = photo["number"]

    lat, lon = photo["gps"]

    marker = folium.CircleMarker(

        location=[
            lat,
            lon
        ],

        radius=5,

        color="#333333",

        weight=1.5,

        fill=True,

        fill_color="#ffffff",

        fill_opacity=0.95,

        tooltip=f"PHOTO #{number}",

    )

    marker.add_to(m)

    marker_names[
        number
    ] = marker.get_name()


marker_click_bindings = "\n".join(
    f'if (typeof {marker_name} !== "undefined") {{ {marker_name}.on("click", () => selectPhoto({number})); }}'
    for number, marker_name in marker_names.items()
)


# ============================================================
# 19. 完整地图范围
# ============================================================

m.fit_bounds(
    coordinates
)


# ============================================================
# 20. Fullscreen
# ============================================================

Fullscreen(
    position="topright"
).add_to(m)


# ============================================================
# 21. 保存基础 HTML
# ============================================================

m.save(
    OUTPUT_HTML
)


# ============================================================
# 22. JS 数据
# ============================================================

js_photos = []

for photo in photos:

    gps = photo["gps"]

    route_gps = photo["route_gps"]

    if gps is None:
        continue

    js_photos.append(
        {
            "number": photo["number"],

            "name": photo["name"],

            "src": photo["src"],

            "lat": gps[0],

            "lon": gps[1],

            "routeLat": (
                route_gps[0]
                if route_gps
                else gps[0]
            ),

            "routeLon": (
                route_gps[1]
                if route_gps
                else gps[1]
            ),

            "marker": marker_names.get(
                photo["number"]
            ),
        }
    )


js_segments = []

for segment in SEGMENTS:

    js_segments.append(
        {
            "name": segment["name"],

            "photos": segment["photos"],
        }
    )


photos_json = json.dumps(
    js_photos,
    ensure_ascii=False
)

segments_json = json.dumps(
    js_segments,
    ensure_ascii=False
)


# ============================================================
# 23. 获取 Folium 实际 map variable
# ============================================================

with open(
    OUTPUT_HTML,
    "r",
    encoding="utf-8"
) as f:

    html = f.read()


map_match = re.search(
    r"(map_[a-f0-9]+)\s*=\s*L\.map",
    html
)


if not map_match:

    raise RuntimeError(
        "无法找到 Folium 地图变量。"
    )


folium_map_name = (
    map_match.group(1)
)


print(
    "Folium Map：",
    folium_map_name
)


# ============================================================
# 24. UI + JavaScript
# ============================================================

ui_html = f"""
<style>

/* =========================================================
   Global
   ========================================================= */

html,
body {{
    margin: 0;
    padding: 0;
    width: 100%;
    height: 100%;
    overflow: hidden;

    font-family:
        -apple-system,
        BlinkMacSystemFont,
        "Segoe UI",
        Arial,
        sans-serif;

    background: #f4f4f4;
}}


/* =========================================================
   Story Panel
   ========================================================= */

.story-panel {{

    position: absolute;

    right: 0;
    top: 0;

    width: 46%;
    height: 100%;

    background: #f7f7f5;

    z-index: 999;

    display: flex;

    flex-direction: column;

    box-shadow:
        -8px 0 30px
        rgba(0,0,0,0.08);
}}


/* =========================================================
   Header
   ========================================================= */

.story-header {{

    padding:
        28px
        30px
        18px
        30px;

    background: #ffffff;

    border-bottom:
        1px solid #e5e5e5;
}}


.eyebrow {{

    font-size: 11px;

    letter-spacing: 2px;

    color: #999;

    text-transform: uppercase;

    margin-bottom: 8px;
}}


.story-title {{

    margin: 0;

    font-size: 26px;

    font-weight: 650;

    letter-spacing: -0.5px;

    color: #1d1d1d;
}}


.story-subtitle {{

    margin-top: 7px;

    font-size: 13px;

    color: #888;
}}


/* =========================================================
   Segment Navigation
   ========================================================= */

.segment-nav {{

    padding:
        14px
        22px;

    display: flex;

    gap: 7px;

    overflow-x: auto;

    background: #ffffff;

    border-bottom:
        1px solid #e8e8e8;

    scrollbar-width: none;
}}


.segment-nav::-webkit-scrollbar {{
    display: none;
}}


.segment-button {{

    flex: none;

    border:
        1px solid #d8d8d8;

    background: #ffffff;

    color: #444;

    border-radius: 18px;

    padding:
        8px
        14px;

    font-size: 12px;

    cursor: pointer;

    transition:
        all 0.2s ease;
}}


.segment-button:hover {{

    background: #f0f0f0;

    transform:
        translateY(-1px);
}}


.segment-button.active {{

    background: #222;

    color: #ffffff;

    border-color: #222;
}}


/* =========================================================
   Location
   ========================================================= */

.location-box {{

    padding:
        18px
        30px
        12px
        30px;
}}


.current-segment {{

    font-size: 20px;

    font-weight: 650;

    color: #222;
}}


.progress-text {{

    margin-top: 5px;

    font-size: 12px;

    color: #999;
}}


/* =========================================================
   Main Photo
   ========================================================= */

.main-photo-wrapper {{

    flex: 1;

    min-height: 0;

    padding:
        8px
        30px
        20px
        30px;

    display: flex;

    flex-direction: column;

    justify-content: center;
}}


.main-photo {{

    width: 100%;

    max-height: 58vh;

    object-fit: contain;

    border-radius: 14px;

    background: #e8e8e8;

    box-shadow:
        0 12px 35px
        rgba(0,0,0,0.12);

    transition:
        opacity 0.25s ease;
}}


.photo-caption {{

    margin-top: 12px;

    display: flex;

    justify-content: space-between;

    align-items: center;
}}


.photo-number {{

    font-size: 13px;

    font-weight: 600;

    color: #333;
}}


.photo-name {{

    max-width: 65%;

    font-size: 11px;

    color: #999;

    overflow: hidden;

    text-overflow: ellipsis;

    white-space: nowrap;
}}


/* =========================================================
   Controls
   ========================================================= */

.controls {{

    padding:
        12px
        30px
        18px
        30px;

    display: flex;

    align-items: center;

    gap: 8px;
}}


.control-button {{

    height: 38px;

    min-width: 38px;

    padding:
        0
        14px;

    border:
        1px solid #d5d5d5;

    background: #ffffff;

    border-radius: 20px;

    color: #222;

    font-size: 13px;

    cursor: pointer;
}}


.play-button {{

    min-width: 92px;

    background: #222;

    color: #fff;

    border-color: #222;
}}


/* =========================================================
   Progress
   ========================================================= */

.progress-wrapper {{

    padding:
        0
        30px
        22px
        30px;
}}


.progress-bar {{

    height: 3px;

    width: 100%;

    background: #dedede;

    border-radius: 3px;

    overflow: hidden;
}}


.progress-fill {{

    height: 100%;

    width: 0%;

    background: #222;

    transition:
        width 0.25s ease;
}}


/* =========================================================
   Filmstrip
   ========================================================= */

.filmstrip {{

    height: 90px;

    display: flex;

    gap: 8px;

    padding:
        0
        30px
        20px
        30px;

    overflow-x: auto;

    scrollbar-width: none;
}}


.filmstrip::-webkit-scrollbar {{
    display: none;
}}


.photo-card {{

    flex: none;

    width: 64px;

    height: 64px;

    position: relative;

    cursor: pointer;

    border-radius: 8px;

    overflow: hidden;

    opacity: 0.5;

    border:
        2px solid transparent;

    transition:
        all 0.2s ease;
}}


.photo-card img {{

    width: 100%;

    height: 100%;

    object-fit: cover;
}}


.photo-card.active {{

    opacity: 1;

    border-color: #222;

    transform:
        translateY(-3px);
}}


.photo-card-number {{

    position: absolute;

    bottom: 0;

    left: 0;

    right: 0;

    padding: 2px 4px;

    font-size: 9px;

    color: #fff;

    background:
        linear-gradient(
            transparent,
            rgba(0,0,0,0.65)
        );

    text-align: right;
}}


/* =========================================================
   CURRENT PHOTO MAP MARKER
   ========================================================= */

.current-photo-marker {{

    width: 38px;

    height: 38px;

    position: relative;

    display: flex;

    align-items: center;

    justify-content: center;
}}


.current-photo-marker .pulse {{

    position: absolute;

    width: 38px;

    height: 38px;

    border:
        2px solid #111;

    border-radius: 50%;

    opacity: 0.25;

    animation:
        mapPulse 1.6s infinite;
}}


.current-photo-marker .dot {{

    width: 12px;

    height: 12px;

    border-radius: 50%;

    background: #111;

    border:
        3px solid #fff;

    box-shadow:
        0 2px 8px
        rgba(0,0,0,0.35);

    z-index: 2;
}}


@keyframes mapPulse {{

    0% {{
        transform: scale(0.65);
        opacity: 0.55;
    }}

    70% {{
        transform: scale(1.35);
        opacity: 0;
    }}

    100% {{
        transform: scale(1.35);
        opacity: 0;
    }}
}}


/* =========================================================
   Mobile
   ========================================================= */

@media (max-width: 900px) {{

    .story-panel {{

        top: 52%;

        width: 100%;

        height: 48%;
    }}

    #map {{

        width: 100%;

        height: 52%;
    }}

    .story-header {{

        padding:
            14px
            18px
            8px
            18px;
    }}

    .story-title {{
        font-size: 19px;
    }}

    .location-box {{

        padding:
            8px
            18px
            4px
            18px;
    }}

    .current-segment {{
        font-size: 16px;
    }}

    .main-photo-wrapper {{

        padding:
            4px
            18px
            8px
            18px;
    }}

    .main-photo {{
        max-height: 22vh;
    }}

    .controls {{

        padding:
            4px
            18px
            8px
            18px;
    }}

    .progress-wrapper {{

        padding:
            0
            18px
            8px
            18px;
    }}

    .filmstrip {{

        height: 60px;

        padding:
            0
            18px
            8px
            18px;
    }}

    .photo-card {{

        width: 45px;

        height: 45px;
    }}
}}

</style>


<!-- =========================================================
     STORY PANEL
     ========================================================= -->

<div class="story-panel">

    <div class="story-header">

        <div class="eyebrow">
            ROUTE STORY
        </div>

        <h1 class="story-title">
            我的徒步轨迹
        </h1>

        <div class="story-subtitle">
            沿路线浏览照片记录
        </div>

    </div>


    <div
        class="segment-nav"
        id="segment-nav"
    >
    </div>


    <div class="location-box">

        <div
            class="current-segment"
            id="current-segment"
        >
            选择一个路段
        </div>

        <div
            class="progress-text"
            id="progress-text"
        >
            点击上方路段开始播放
        </div>

    </div>


    <div class="main-photo-wrapper">

        <img
            id="main-photo"
            class="main-photo"
            src=""
            alt=""
        >

        <div class="photo-caption">

            <div
                id="photo-number"
                class="photo-number"
            >
            </div>

            <div
                id="photo-name"
                class="photo-name"
            >
            </div>

        </div>

    </div>


    <div class="controls">

        <button
            class="control-button"
            onclick="previousPhoto()"
        >
            ←
        </button>

        <button
            id="play-button"
            class="control-button play-button"
            onclick="togglePlay()"
        >
            ▶ 播放
        </button>

        <button
            class="control-button"
            onclick="nextPhoto()"
        >
            →
        </button>

    </div>


    <div class="progress-wrapper">

        <div class="progress-bar">

            <div
                id="progress-fill"
                class="progress-fill"
            >
            </div>

        </div>

    </div>


    <div
        class="filmstrip"
        id="filmstrip"
    >
    </div>

</div>


<script>

/* =========================================================
   DATA
   ========================================================= */

const photos = {photos_json};

const segments = {segments_json};


/* =========================================================
   STATE
   ========================================================= */

let currentSegmentIndex = 0;

let currentPhotoIndex = 0;

let isPlaying = false;

let playTimer = null;


/* =========================================================
   MAP
   ========================================================= */

const mapObject = {folium_map_name};


function getMapPanelPadding() {{

    if (window.innerWidth <= 900) {{
        return [0, 0];
    }}

    return [
        window.innerWidth * 0.46,
        0
    ];

}}


function getMapPointOffset() {{

    if (window.innerWidth <= 900) {{
        return [0, 0];
    }}

    return [
        window.innerWidth * 0.23,
        0
    ];

}}


function getMapPointCenter(lat, lon, zoom) {{

    const point =
        mapObject.project(
            [lat, lon],
            zoom
        );

    return mapObject.unproject(
        point.add(
            getMapPointOffset()
        ),
        zoom
    );

}}


mapObject.fitBounds(
    mapObject.getBounds(),
    {{
        paddingBottomRight: getMapPanelPadding(),
        animate: false
    }}
);


/* =========================================================
   CURRENT LOCATION MARKER
   ========================================================= */

let currentMarker = null;


/* =========================================================
   Create current marker
   ========================================================= */

function createCurrentMarker(photo) {{

    if (!photo) {{
        return;
    }}

    const lat =
        photo.routeLat !== null
        ? photo.routeLat
        : photo.lat;

    const lon =
        photo.routeLon !== null
        ? photo.routeLon
        : photo.lon;


    const icon =
        L.divIcon({{

            className: "",

            html:
                '<div class="current-photo-marker">' +
                    '<div class="pulse"></div>' +
                    '<div class="dot"></div>' +
                '</div>',

            iconSize: [
                38,
                38
            ],

            iconAnchor: [
                19,
                19
            ]

        }});


    if (currentMarker) {{

        currentMarker.setLatLng([
            lat,
            lon
        ]);

        currentMarker.setIcon(
            icon
        );

    }} else {{

        currentMarker =
            L.marker(
                [
                    lat,
                    lon
                ],
                {{
                    icon: icon,
                    zIndexOffset: 1000
                }}
            ).addTo(
                mapObject
            );
    }}

}}


/* =========================================================
   Photo lookup
   ========================================================= */

function getPhoto(number) {{

    return photos.find(
        p => p.number === number
    );

}}


/* =========================================================
   Get valid photos in segment
   ========================================================= */

function getSegmentPhotos() {{

    const segment =
        segments[
            currentSegmentIndex
        ];

    return segment.photos.filter(
        number =>
            getPhoto(number)
            !== undefined
    );

}}


/* =========================================================
   Render filmstrip
   ========================================================= */

function renderFilmstrip() {{

    const filmstrip =
        document.getElementById(
            "filmstrip"
        );

    filmstrip.innerHTML = "";

    const numbers =
        getSegmentPhotos();


    numbers.forEach(
        number => {{

            const photo =
                getPhoto(number);

            if (!photo) {{
                return;
            }}


            const card =
                document.createElement(
                    "div"
                );

            card.className =
                "photo-card";

            card.dataset.number =
                number;

            card.onclick =
                () => selectPhoto(number);


            const img =
                document.createElement(
                    "img"
                );

            img.src =
                photo.src;

            img.loading =
                "lazy";

            img.alt =
                `Photo #${{number}}`;


            const label =
                document.createElement(
                    "div"
                );

            label.className =
                "photo-card-number";

            label.innerText =
                `#${{number}}`;


            card.appendChild(img);

            card.appendChild(label);

            filmstrip.appendChild(card);

        }}
    );

}}


/* =========================================================
   Segment navigation
   ========================================================= */

const nav =
    document.getElementById(
        "segment-nav"
    );


segments.forEach(
    (segment, index) => {{

        const button =
            document.createElement(
                "button"
            );

        button.className =
            "segment-button";

        button.innerText =
            `${{segment.name}} · ${{segment.photos.length}}`;

        button.onclick =
            () => selectSegment(index);

        nav.appendChild(button);

    }}
);


/* =========================================================
   Select Segment
   ========================================================= */

function selectSegment(index) {{

    stopPlaying();


    currentSegmentIndex =
        index;

    currentPhotoIndex =
        0;


    document
        .querySelectorAll(
            ".segment-button"
        )
        .forEach(
            (button, i) => {{

                button.classList.toggle(
                    "active",
                    i === index
                );

            }}
        );


    renderFilmstrip();


    const validNumbers =
        getSegmentPhotos();


    if (
        validNumbers.length === 0
    ) {{
        return;
    }}


    const points =
        validNumbers
            .map(
                number =>
                    getPhoto(number)
            )
            .filter(
                photo =>
                    photo &&
                    photo.lat !== null
            )
            .map(
                photo =>
                    [
                        photo.routeLat,
                        photo.routeLon
                    ]
            );


    if (
        points.length > 0
    ) {{

        mapObject.fitBounds(
            points,
            {{
                padding: [
                    70,
                    70
                ],

                paddingBottomRight: getMapPanelPadding(),

                maxZoom: 17,

                animate: true,

                duration: 1.2
            }}
        );

    }}


    showSegmentPhoto();

}}


/* =========================================================
   Show Current Photo
   ========================================================= */

function showSegmentPhoto() {{

    const validNumbers =
        getSegmentPhotos();


    if (
        validNumbers.length === 0
    ) {{
        return;
    }}


    if (
        currentPhotoIndex >=
        validNumbers.length
    ) {{

        currentPhotoIndex =
            validNumbers.length - 1;
    }}


    const number =
        validNumbers[
            currentPhotoIndex
        ];


    const photo =
        getPhoto(number);


    if (!photo) {{
        return;
    }}


    /* -------------------------------------------------------
       Text
       ------------------------------------------------------- */

    document
        .getElementById(
            "current-segment"
        )
        .innerText =
            segments[
                currentSegmentIndex
            ].name;


    document
        .getElementById(
            "progress-text"
        )
        .innerText =
            `照片 ${{currentPhotoIndex + 1}} / ${{validNumbers.length}} · #${{number}}`;


    document
        .getElementById(
            "photo-number"
        )
        .innerText =
            `PHOTO #${{number}}`;


    document
        .getElementById(
            "photo-name"
        )
        .innerText =
            photo.name;


    /* -------------------------------------------------------
       Main Image
       ------------------------------------------------------- */

    const mainPhoto =
        document.getElementById(
            "main-photo"
        );


    mainPhoto.style.opacity =
        "0.25";


    setTimeout(
        () => {{

            mainPhoto.src =
                photo.src;

            mainPhoto.alt =
                photo.name;

            mainPhoto.style.opacity =
                "1";

        }},
        100
    );


    /* -------------------------------------------------------
       Filmstrip Active
       ------------------------------------------------------- */

    document
        .querySelectorAll(
            ".photo-card"
        )
        .forEach(
            card => {{

                card.classList.toggle(
                    "active",
                    Number(
                        card.dataset.number
                    ) === number
                );

            }}
        );


    /* -------------------------------------------------------
       Progress
       ------------------------------------------------------- */

    const progress =
        (
            currentPhotoIndex /
            Math.max(
                validNumbers.length - 1,
                1
            )
        ) * 100;


    document
        .getElementById(
            "progress-fill"
        )
        .style.width =
            progress + "%";


    /* -------------------------------------------------------
       Scroll Filmstrip
       ------------------------------------------------------- */

    const activeCard =
        document.querySelector(
            `.photo-card[data-number="${{number}}"]`
        );


    if (activeCard) {{

        activeCard.scrollIntoView(
            {{
                behavior: "smooth",

                block: "nearest",

                inline: "center"
            }}
        );

    }}


    /* -------------------------------------------------------
       MAP CURRENT POINT
       ------------------------------------------------------- */

    createCurrentMarker(
        photo
    );


    /* -------------------------------------------------------
       MAP FLY TO CURRENT ROUTE POINT
       ------------------------------------------------------- */

    const targetLat =
        photo.routeLat !== null
        ? photo.routeLat
        : photo.lat;


    const targetLon =
        photo.routeLon !== null
        ? photo.routeLon
        : photo.lon;


    if (
        targetLat !== null &&
        targetLon !== null
    ) {{

        mapObject.stop();

        const targetZoom = 17;

        const targetCenter =
            getMapPointCenter(
                targetLat,
                targetLon,
                targetZoom
            );

        mapObject.flyTo(
            targetCenter,

            targetZoom,

            {{
                duration: 0.45,

                easeLinearity: 0.25
            }}
        );

    }}

}}


/* =========================================================
   Next Photo
   ========================================================= */

function nextPhoto() {{

    const validNumbers =
        getSegmentPhotos();


    if (
        validNumbers.length === 0
    ) {{
        return;
    }}


    if (
        currentPhotoIndex <
        validNumbers.length - 1
    ) {{

        currentPhotoIndex++;

        showSegmentPhoto();

    }}
    else {{

        stopPlaying();

    }}

}}


/* =========================================================
   Previous Photo
   ========================================================= */

function previousPhoto() {{

    if (
        currentPhotoIndex > 0
    ) {{

        currentPhotoIndex--;

        showSegmentPhoto();

    }}

}}


/* =========================================================
   Toggle Play
   ========================================================= */

function togglePlay() {{

    if (isPlaying) {{

        stopPlaying();

    }} else {{

        startPlaying();

    }}

}}


/* =========================================================
   Start Playing
   ========================================================= */

function startPlaying() {{

    const validNumbers =
        getSegmentPhotos();


    if (
        validNumbers.length === 0
    ) {{
        return;
    }}


    isPlaying = true;


    document
        .getElementById(
            "play-button"
        )
        .innerText =
            "Ⅱ 暂停";


    playTimer =
        setInterval(
            () => {{

                if (
                    currentPhotoIndex >=
                    validNumbers.length - 1
                ) {{

                    stopPlaying();

                    return;

                }}


                currentPhotoIndex++;

                showSegmentPhoto();

            }},
            1000
        );

}}


/* =========================================================
   Stop Playing
   ========================================================= */

function stopPlaying() {{

    isPlaying = false;


    if (playTimer) {{

        clearInterval(
            playTimer
        );

        playTimer = null;

    }}


    document
        .getElementById(
            "play-button"
        )
        .innerText =
            "▶ 播放";

}}


/* =========================================================
   Select Photo
   ========================================================= */

function selectPhoto(number) {{

    const photo =
        getPhoto(number);


    if (!photo) {{
        return;
    }}


    let foundSegment =
        -1;

    let foundIndex =
        -1;


    segments.forEach(
        (
            segment,
            segmentIndex
        ) => {{

            const validNumbers =
                segment.photos.filter(
                    n =>
                        getPhoto(n)
                        !== undefined
                );


            const index =
                validNumbers.indexOf(
                    number
                );


            if (index !== -1) {{

                foundSegment =
                    segmentIndex;

                foundIndex =
                    index;

            }}

        }}
    );


    if (
        foundSegment !== -1
    ) {{

        currentSegmentIndex =
            foundSegment;

        currentPhotoIndex =
            foundIndex;


        document
            .querySelectorAll(
                ".segment-button"
            )
            .forEach(
                (button, i) => {{

                    button.classList.toggle(
                        "active",
                        i === foundSegment
                    );

                }}
            );


        renderFilmstrip();

    }}


    showSegmentPhoto();

}}


/* =========================================================
   Initialize
   ========================================================= */

if (
    segments.length > 0
) {{

    selectSegment(0);

}}


{marker_click_bindings}

</script>
"""


# ============================================================
# 25. 插入 UI
# ============================================================

html = html.replace(
    "</html>",
    ui_html + "\n</html>"
)


# ============================================================
# 26. 写回 HTML
# ============================================================

with open(
    OUTPUT_HTML,
    "w",
    encoding="utf-8"
) as f:

    f.write(html)


# ============================================================
# 27. 完成
# ============================================================

print()
print("=" * 70)
print("HTML 生成完成")
print("=" * 70)

print(
    "轨迹点：",
    len(coordinates)
)

print(
    "照片：",
    len(photos)
)

print(
    "GPS 照片：",
    gps_count
)

print(
    "图片目录：",
    PHOTO_DIR
)

print(
    "输出：",
    OUTPUT_HTML
)

print("=" * 70)