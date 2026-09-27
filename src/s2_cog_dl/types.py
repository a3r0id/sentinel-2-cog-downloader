from typing import Sequence, Union, Tuple, List, Optional, Dict, Any

import numpy as np
import xarray as xr

DateType = Union[str, Tuple[str, str], List[str]]
BBoxType = Union[List[float], Tuple[float, float, float, float]]
ArrayLike = Union[xr.DataArray, np.ndarray]
CRSType = Union[str, int, dict, None]
BandType = Union[str, Sequence[str]]
ChunksType = Optional[Dict[str, Any]]
