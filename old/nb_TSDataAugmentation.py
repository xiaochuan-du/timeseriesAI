#AUTOGENERATED! DO NOT EDIT! file to edit: ./TSDataAugmentation.ipynb (unless otherwise specified)

import copy
import numpy as np
import random
from functools import partial


try: from exp.nb_TSUtilities import *
except ImportError: from .nb_TSUtilities import *

try: from exp.nb_TSBasicData import *
except ImportError: from .nb_TSBasicData import *

device = 'cuda' if torch.cuda.is_available() else 'cpu'


def shuffle_HLs(ts, **kwargs):
    line = copy(ts)
    pos_rand_list = np.random.choice(
        np.arange(ts.shape[-1] // 4),
        size=random.randint(0, ts.shape[-1] // 4),
        replace=False)
    rand_list = pos_rand_list * 4
    highs = rand_list + 1
    lows = highs + 1
    a = np.vstack([highs, lows]).flatten('F')
    b = np.vstack([lows, highs]).flatten('F')
    line[..., a] = line[..., b]
    return line

setattr(shuffle_HLs, 'use_on_y', False)


def get_diff(a):
    return np.concatenate((np.zeros(a.shape[-2])[:, None], np.diff(a)), axis=1).astype(np.float32)

setattr(get_diff, 'use_on_y', False)


class TSTransform():
    "Utility class for adding probability and wrapping support to transform `func`."
    _wrap=None
    order=0
    def __init__(self, func:Callable, order:Optional[int]=None):
        "Create a transform for `func` and assign it an priority `order`, attach to `TS` class."
        if order is not None: self.order=order
        self.func=func
        self.func.__name__ = func.__name__[1:] #To remove the _ that begins every transform function.
        functools.update_wrapper(self, self.func)
        self.func.__annotations__['return'] = TSItem
        self.params = copy(func.__annotations__)
        self.def_args = _get_default_args(func)
        setattr(TSItem, func.__name__, lambda x, *args, **kwargs: self.calc(x, *args, **kwargs))

    def __call__(self, *args:Any, p:float=1., is_random:bool=True, use_on_y:bool=False, **kwargs:Any)->TSItem:
        "Calc now if `args` passed; else create a transform called prob `p` if `random`."
        if args: return self.calc(*args, **kwargs)
        else: return RandTransform(self, kwargs=kwargs, is_random=is_random, use_on_y=use_on_y, p=p)

    def calc(self, x:TSItem, *args:Any, **kwargs:Any)->Image:
        "Apply to image `x`, wrapping it if necessary."
        if self._wrap: return getattr(x, self._wrap)(self.func, *args, **kwargs)
        else:          return self.func(x, *args, **kwargs)

    @property
    def name(self)->str: return self.__class__.__name__

    def __repr__(self)->str: return f'{self.name} ({self.func.__name__})'


def _get_default_args(func:Callable):
    return {k: v.default
            for k, v in inspect.signature(func).parameters.items()
            if v.default is not inspect.Parameter.empty}


# 1) Those that slightly modify the time series in the x and/ or y-axes:
# - TSmagnoise == TSjittering (1)
# - TSmagscale (1)
# - TSmagwarp (1)
# - TStimenoise (1)
# - TStimewarp (1)

# 2) And those that remove certain part of the time series (a section or channel):
# - TSlookback
# - TStimestepsout (1)
# - TSchannelout
# - TScutout (2)
# - TScrop (1)
# - TSwindowslice (3)
# - TSzoom (1)

# All of them can be used independently or in combination. In this section, you'll see how these transforms work.

# (1) Adapted from/ inspired by Um, T. T., Pfister, F. M. J., Pichler, D., Endo, S., Lang, M., Hirche, S., ... & Kulić, D. (2017). Data augmentation of wearable sensor data for parkinson's disease monitoring using convolutional neural networks. arXiv preprint arXiv:1706.00527. (includes: Jittering, Scaling, Magnitude-Warping, Time-warping, Random Sampling, among others.

# (2) Inspired by DeVries, T., & Taylor, G. W. (2017). Improved regularization of convolutional neural networks with cutout. arXiv preprint arXiv:1708.04552.

# (3) Inspired by Le Guennec, A., Malinowski, S., & Tavenard, R. (2016, September). Data augmentation for time series classification using convolutional neural networks.



def _ynoise(ts, alpha=.05, add=True):
    seq_len = ts.shape[-1]
    if add:
        noise = torch.normal(0, alpha, (1, ts.shape[-1]), dtype=ts.dtype, device=ts.device)
        return ts + noise
    else:
        scale = torch.ones(seq_len) + torch.normal(0, alpha, (1, ts.shape[-1]), dtype=ts.dtype, device=ts.device)
        return ts * scale

TSynoise = TSTransform(_ynoise)
TSmagnoise = TSTransform(_ynoise)
TSjittering = TSTransform(_ynoise)

from scipy.interpolate import CubicSpline
def random_curve_generator(ts, alpha=.1, order=4, noise=None):
    seq_len = ts.shape[-1]
    x = np.linspace(- seq_len, 2 * seq_len - 1, 3 * (order - 1) + 1, dtype=int)
    x2 = np.random.normal(loc=1.0, scale=alpha, size=len(x))
    f = CubicSpline(x, x2, axis=1)
    return f(np.arange(seq_len))

def random_cum_curve_generator(ts, alpha=.1, order=4, noise=None):
    x = random_curve_generator(ts, alpha=alpha, order=order, noise=noise).cumsum()
    x -= x[0]
    x /= x[-1]
    x = np.clip(x, 0, 1)
    return x * (ts.shape[-1] - 1)

def random_cum_noise_generator(ts, alpha=.1, noise=None):
    seq_len = ts.shape[-1]
    x = (np.ones(seq_len) + np.random.normal(loc=0, scale=alpha, size=seq_len)).cumsum()
    x -= x[0]
    x /= x[-1]
    x = np.clip(x, 0, 1)
    return x * (ts.shape[-1] - 1)

from scipy.interpolate import CubicSpline
def _xwarp(ts, alpha=.05, order=4):
    f = CubicSpline(np.arange(ts.shape[-1]), ts, axis=1)
    new_x = random_cum_curve_generator(ts, alpha=alpha, order=order)
    return ts.new(f(new_x))

TSxwarp = TSTransform(_xwarp)
TStimewarp = TSTransform(_xwarp)

from scipy.interpolate import CubicSpline
def _ywarp(ts, alpha=.05, order=4):
    f2 = CubicSpline(np.arange(ts.shape[-1]), ts, axis=1)
    y_mult = random_curve_generator(ts, alpha=alpha, order=order)
    return ts * ts.new(y_mult)

TSywarp = TSTransform(_ywarp)
TSmagwarp = TSTransform(_ywarp)

from scipy.interpolate import CubicSpline
def _scale(ts, alpha=.1):
    rand = 1 - torch.rand(1)[0] * 2
    scale = 1 + torch.abs(rand) * alpha
    if rand < 0: scale = 1 / scale
    return ts * scale

TSmagscale = TSTransform(_scale)

from scipy.interpolate import CubicSpline
def _xnoisewarp(ts, alpha=.1):
    f = CubicSpline(np.arange(ts.shape[-1]), ts, axis=1)
    new_x = random_cum_noise_generator(ts, alpha=alpha)
    return ts.new(f(new_x))

TSxnoisewarp = TSTransform(_xnoisewarp)
TStimenoise = TSTransform(_xnoisewarp)

def get_TS_xy_tfms():
    return [[TStimewarp(p=.5), TSmagwarp(p=.5), TStimenoise(p=.5), TSmagnoise(p=.5)], []]


def _rand_lookback(ts, alpha=.2):
    new_ts = ts.clone()
    lambd = np.random.beta(alpha, alpha)
    lambd = min(lambd, 1 - lambd)
    lookback_per = int(lambd * new_ts.shape[-1])
    new_ts[:, :lookback_per] = 0
    return new_ts

TSlookback = TSTransform(_rand_lookback)

def _random_channel_out(ts, alpha=.2):
    input_ch = ts.shape[0]
    if input_ch == 1: return ts
    new_ts = ts.clone()
    out_ch = np.random.choice(np.arange(input_ch),
                              min(input_ch - 1, int(np.random.beta(alpha, 1) * input_ch)),
                              replace=False)
    new_ts[out_ch] = 0
    return new_ts

TSchannelout = TSTransform(_random_channel_out)

def _cutout(ts, perc=.1):
    if perc >= 1 or perc <= 0: return ts
    seq_len = ts.shape[-1]
    new_ts = ts.clone()
    win_len = int(perc * seq_len)
    start = np.random.randint(-win_len + 1, seq_len)
    end = start + win_len
    start = max(0, start)
    end = min(end, seq_len)
    new_ts[..., start:end] = 0
    return new_ts

TScutout= TSTransform(_cutout)

def _timesteps_out(ts, perc=.1):
    if perc >= 1 or perc <= 0: return ts
    seq_len = ts.shape[-1]
    timesteps = np.sort(np.random.choice(np.arange(seq_len), int(seq_len * (1 - perc)), replace=False))
    return ts[..., timesteps]

TStimestepsout = TSTransform(_timesteps_out)

def _crop(ts, perc=.9):
    if perc >= 1 or perc <= 0: return ts
    seq_len = ts.shape[-1]
    win_len = int(seq_len * perc)
    new_ts = torch.zeros((ts.shape[-2], win_len))
    start = np.random.randint(-win_len + 1, seq_len)
    end = start + win_len
    start = max(0, start)
    end = min(end, seq_len)
    new_ts[:, - end + start :] = ts[:, start : end]
    return new_ts

TScrop = TSTransform(_crop)

def _window_slice(ts, perc=.9):
    if perc == 1.0 or perc == 0: return ts
    seq_len = ts.shape[-1]
    win_len = int(seq_len * perc)
    start = np.random.randint(0, seq_len - win_len)
    return ts[:, start : start + win_len]

TSwindowslice = TSTransform(_window_slice)

def _random_zoom(ts, alpha=.2):
    if alpha == 1.0: return a
    seq_len = ts.shape[-1]
    lambd = np.random.beta(alpha, alpha)
    lambd = max(lambd, 1 - lambd)
    win_len = int(seq_len * lambd)
    if win_len == seq_len: start = 0
    else: start = np.random.randint(0, seq_len - win_len)
    y = ts[:, start : start + win_len]
    f = CubicSpline(np.arange(y.shape[-1]), y, axis=1)
    return ts.new(f(np.linspace(0, win_len - 1, num=seq_len)))

TSzoom = TSTransform(_random_zoom)

def get_TS_remove_tfms():
    return [[TSlookback(p=.5), TStimestepsout(p=.5), TSchannelout(p=.5), TScutout(p=.5),
            TScrop(p=.5), TSwindowslice(p=.5), TSzoom(p=.5)], []]