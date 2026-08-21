import cadquery as cq
from click_cadquery import BuildParam
from click_cadquery.git import version_number as ver


class Param(BuildParam):
    width: int = 100
    height: int = 100
    depth: int = 100
    thickness: float = 2.0

    @property
    def filename(self) -> str:
        return f"v{ver()}-{self.width}w{self.height}h{self.depth}d{self.thickness}t.stl"


def build(param: Param) -> cq.Workplane:
    result = cq.Workplane("XY")

    result = result.box(
        length=param.depth,
        height=param.height,
        width=param.width,
    )

    result = result.faces(">Z").shell(param.thickness, kind="intersection")

    fillet = param.thickness / 2
    result = result.edges("|Z").fillet(fillet)

    return result
