from click_cadquery import define_app

from .main import Param, build

main = define_app(Param, build)
