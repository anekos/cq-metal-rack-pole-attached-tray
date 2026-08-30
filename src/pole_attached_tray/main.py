from collections.abc import Sequence
from typing import Literal, cast

import cadquery as cq
from cadquery.occ_impl.shapes import Shape
from cadquery.selectors import Selector
from click_cadquery import BuildParam
from click_cadquery.git import version_number as ver
from click_cadquery.partition import (
    SYNTAX,
    PartitionExpr,
    PartitionParam,
    partition_field,
    walls_solid,
)
from pydantic import Field


class Param(BuildParam, PartitionParam):
    part: Literal["both", "tray", "holder"] = Field(
        "both", description="出力する部品 (両方 / トレイだけ / 固定具だけ)"
    )
    pole_diameter: float = Field(25.0, description="ポール (支柱) の直径 [mm]")
    thickness: float = Field(3.0, description="トレイの壁厚・固定具の腕の肉厚 [mm]")
    height: float = Field(40.0, description="トレイの Z 方向 (ポール軸方向) の高さ")
    wing_width: float = Field(
        15.0, description="固定具の耳 (結束バンド穴のある平板部) の幅 [mm]"
    )
    tray_width: float = Field(150.0, description="トレイの幅 (X) [mm]")
    tray_depth: float = Field(100.0, description="トレイの奥行き (Y) [mm]")
    front_height: float = Field(
        10.0, description="トレイ手前側の壁の高さ [mm] (取り出しやすいよう低くする)"
    )
    back_flat_depth: float = Field(
        15.0,
        description="トレイ背面側で全高 (height) のまま残す奥行き [mm]。"
        "残りは手前に向かって front_height まで斜めに下がる",
    )
    hole_diameter: float = Field(5.0, description="結束バンド穴の直径 [mm]")
    hole_margin: float = Field(
        10.0, description="結束バンド穴 (上側) の上端からの距離 [mm]"
    )
    hole_pitch: float = Field(
        20.0,
        description="上下の結束バンド穴の間隔 [mm]。height を変えても間隔は変わらない",
    )
    partition: PartitionExpr = partition_field(
        "1", description=f"トレイ内部の仕切りレイアウト: {SYNTAX}"
    )
    spacing: float = Field(
        10.0, description="part=both のときにトレイと固定具を並べる間隔 [mm]"
    )

    @property
    def pole_radius(self) -> float:
        return self.pole_diameter / 2

    @property
    def outer_radius(self) -> float:
        """ポールを抱き込む円弧の外径。内径 (pole_radius) + 肉厚。"""
        return self.pole_radius + self.thickness

    @property
    def hole_x(self) -> float:
        """結束バンド穴の中心の X 座標 (円弧の外径から耳の中央まで)。"""
        return self.outer_radius + self.wing_width / 2

    @property
    def inner_width(self) -> float:
        """トレイの内寸幅 (X)。partition の解決に使う (PartitionParam が要求する)。"""
        return self.tray_width - 2 * self.thickness

    @property
    def inner_depth(self) -> float:
        """トレイの内寸奥行き (Y)。partition の解決に使う (PartitionParam が要求する)。"""
        return self.tray_depth - 2 * self.thickness

    @property
    def holder_height(self) -> float:
        """固定具の高さ。トレイの height とは独立で、上下の穴を hole_margin ぶんの
        余白を持たせて収められる最小限の高さ (穴の間隔から自ずと決まる)。"""
        return self.hole_pitch + 2 * self.hole_margin

    @property
    def filename(self) -> str:
        part = "" if self.part == "both" else f"-{self.part}"
        return f"v{ver()}-{self.pole_diameter}pole{self.thickness}t{part}.stl"


def _corner_fillet_radius(thickness: float) -> float:
    """縦エッジのフィレット半径。thickness/2 ちょうどだと OCCT が失敗することがあるので少し控えめにする。"""
    return thickness / 2 * 0.9


class _VerticalEdgeAtAbsX(Selector):
    """|Z (鉛直) の直線エッジのうち、x = ±x_abs にあるものだけを選ぶ。

    円弧との接続部などにできる短い縦エッジを避け、外側の角だけを選別するために使う。
    """

    def __init__(self, x_abs: float, tol: float = 1e-3) -> None:
        self.x_abs = x_abs
        self.tol = tol

    def filter(self, object_list: Sequence[Shape]) -> list[Shape]:  # type: ignore[override]
        out = []
        for obj in object_list:
            bb = obj.BoundingBox()
            if (
                abs(bb.xmax - bb.xmin) < self.tol
                and abs(abs(bb.xmin) - self.x_abs) < self.tol
            ):
                out.append(obj)
        return out


def _half_cylinder(height: float, radius: float, keep_positive_y: bool) -> cq.Workplane:
    """半径 radius・高さ height の円柱を Y=0 の平面で半分に割ったもの。"""
    big = radius * 4 + height
    cylinder = cq.Workplane("XY").cylinder(height, radius, centered=(True, True, False))
    cutter = cq.Workplane("XY").box(big, big, height, centered=(True, True, False))
    cutter = cutter.translate((0, -big / 2 if keep_positive_y else big / 2, 0))
    return cylinder.cut(cutter)


def _wing_holes(param: Param, wall_y: float, part_height: float) -> cq.Workplane:
    """左右の耳 (x = ±hole_x) に、上下 2 個ずつ、Y 軸方向に貫通する穴。

    Z 位置は part_height の上端から hole_margin・hole_pitch で決まる
    (トレイと固定具で高さが異なっても、上端をそろえれば穴は一致する)。
    """
    r = param.hole_diameter / 2
    length = param.thickness + 2.0
    z_top = part_height - param.hole_margin
    z_bottom = z_top - param.hole_pitch
    holes = None
    for sx in (-1, 1):
        for z in (z_bottom, z_top):
            hole = (
                cq.Workplane("XY")
                .cylinder(length, r, direct=(0, 1, 0), centered=(True, True, True))
                .translate((sx * param.hole_x, wall_y, z))
            )
            holes = hole if holes is None else holes.union(hole)
    return cast(cq.Workplane, holes)


def build_holder(param: Param) -> cq.Workplane:
    """ポールに抱きつく円弧 + 結束バンド用の耳を持つ固定具。

    断面 (XY) は (耳の帯板 ∪ 外径の半円) − 内径の半円 で、
    Y=0 が耳の付け根 (トレイに接する面)、Y>0 側にポールを抱き込む。
    """
    pole_r = param.pole_radius
    outer_r = param.outer_radius
    half_width = outer_r + param.wing_width
    holder_height = param.holder_height

    wing = cq.Workplane("XY").box(
        2 * half_width, param.thickness, holder_height, centered=(True, False, False)
    )
    outer_half = _half_cylinder(holder_height, outer_r, keep_positive_y=True)

    result = wing.union(outer_half)
    result = result.cut(
        cq.Workplane("XY").cylinder(holder_height, pole_r, centered=(True, True, False))
    )
    result = (
        result.edges("|Z")
        .edges(_VerticalEdgeAtAbsX(half_width))
        .fillet(_corner_fillet_radius(param.thickness))
    )
    result = result.cut(
        _wing_holes(param, wall_y=param.thickness / 2, part_height=holder_height)
    )

    return result


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def _tray_ramp_keep_solid(param: Param) -> cq.Workplane:
    """トレイの残す側 (斜めカットの下側) を表すソリッド。これと intersect して壁の上端を落とす。

    手前 (-Y 端) は front_height、背面 (+Y 端から back_flat_depth の範囲) は height のまま。
    その間は直線的に高さが変化する。
    """
    half_depth = param.tray_depth / 2
    y_top = half_depth - param.back_flat_depth
    raw_profile = [
        (-half_depth, 0.0),
        (-half_depth, param.front_height),
        (y_top, param.height),
        (half_depth, param.height),
        (half_depth, 0.0),
    ]
    profile = [
        p
        for i, p in enumerate(raw_profile)
        if i == 0 or _distance(p, raw_profile[i - 1]) > 1e-9
    ]
    over_extrude = param.tray_width / 2 + param.thickness + 10.0
    return cq.Workplane("YZ").polyline(profile).close().extrude(over_extrude, both=True)


def _tray_dividers(param: Param) -> cq.Workplane | None:
    """トレイ内部の仕切り板 (partition レイアウトから生成)。

    click_cadquery.partition が壁を Z=0 起点・高さ height で作るので、
    外壁と同じ斜めプロファイルに intersect するだけでよい。Y 方向に伸びる壁
    (axis="x") は外壁と同じ角度で傾斜し、X 方向に伸びる壁 (axis="y") は
    置かれた Y 位置での外壁の高さに合わせて水平にカットされる。
    """
    walls = walls_solid(param.layout(), height=param.height)
    if walls is None:
        return None
    return walls.intersect(_tray_ramp_keep_solid(param))


def build_tray(param: Param) -> cq.Workplane:
    """上面が開いたトレイ。背面 (+Y 側) の中央にポールを抱き込む半円柱を持つ。

    手前の壁は取り出しやすいよう低く、背面から斜めに下がる (装飾ではなく機能)。
    背面の半円柱は固定具側の円弧と対になってポールを両側から挟み込むためのもので、
    これが無いとポールに接する面が平らな切り欠きだけになり、しっかり固定できない。
    """
    pole_r = param.pole_radius
    outer_r = param.outer_radius
    center_y = param.tray_depth / 2

    result = cq.Workplane("XY").box(
        param.tray_width, param.tray_depth, param.height, centered=(True, True, False)
    )
    result = result.faces(">Z").shell(-param.thickness, kind="intersection")
    result = result.edges("|Z").fillet(_corner_fillet_radius(param.thickness))
    result = result.intersect(_tray_ramp_keep_solid(param))

    dividers = _tray_dividers(param)
    if dividers is not None:
        result = result.union(dividers)

    # 半円柱を収める分だけ大きくくり抜いてから、ポール側 (-Y 向き) に半円柱を足す
    clearance = cq.Workplane("XY").cylinder(
        param.height, outer_r, centered=(True, True, False)
    )
    result = result.cut(clearance.translate((0, center_y, 0)))

    pole_hug = _half_cylinder(param.height, outer_r, keep_positive_y=False)
    result = result.union(pole_hug.translate((0, center_y, 0)))

    bore = cq.Workplane("XY").cylinder(
        param.height, pole_r, centered=(True, True, False)
    )
    result = result.cut(bore.translate((0, center_y, 0)))

    wall_y = param.tray_depth / 2 - param.thickness / 2
    result = result.cut(_wing_holes(param, wall_y=wall_y, part_height=param.height))

    return result


def build(param: Param) -> cq.Workplane:
    if param.part == "tray":
        return build_tray(param)
    if param.part == "holder":
        return build_holder(param)

    tray = build_tray(param)
    holder = build_holder(param)

    tray_bb = cast(cq.Shape, tray.val()).BoundingBox()
    holder_bb = cast(cq.Shape, holder.val()).BoundingBox()
    dx = tray_bb.xmax + param.spacing - holder_bb.xmin
    return tray.add(holder.translate((dx, 0, 0)))
