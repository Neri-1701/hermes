"""Family-specific extractors selected after localization."""

from hermes.domain.materials import MaterialFamily
from hermes.services.material_parsing.extractors.base import MaterialExtractor
from hermes.services.material_parsing.extractors.elbows import ElbowExtractor
from hermes.services.material_parsing.extractors.flanges import FlangeExtractor
from hermes.services.material_parsing.extractors.gaskets import GasketExtractor
from hermes.services.material_parsing.extractors.pipes import PipeExtractor
from hermes.services.material_parsing.extractors.studs import StudExtractor

EXTRACTORS: dict[MaterialFamily, MaterialExtractor] = {
    MaterialFamily.STUDS: StudExtractor(),
    MaterialFamily.GASKETS: GasketExtractor(),
    MaterialFamily.PIPE: PipeExtractor(),
    MaterialFamily.FLANGES: FlangeExtractor(),
    MaterialFamily.ELBOWS: ElbowExtractor(),
}

__all__ = ["EXTRACTORS"]
