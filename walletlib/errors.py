"""错误类型定义。"""


class WalletError(Exception):
    """库内所有错误的基类。"""


class InvalidAddressError(WalletError):
    """地址文本不符合所属网络的编码规则。"""


class UnsupportedNetworkError(WalletError):
    """网络名称不在支持列表内。"""


class BatchTooLargeError(WalletError):
    """单批条目数超过上限。"""
