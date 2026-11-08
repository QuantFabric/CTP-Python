# -*- coding: utf-8 -*-
import ctp_wrap.ctp_md as ctp_md
import traceback
import time
import threading

# ============================================================
# 格式化辅助
# ============================================================
_DBL_INVALID = 1e300

def _fd(v, digits=2):
    """CTP 行情用 DBL_MAX 表示无效值，显示为 N/A"""
    if v is None:
        return "None"
    try:
        if v > _DBL_INVALID or v < -_DBL_INVALID:
            return "N/A"
        return f"{v:.{digits}f}"
    except Exception:
        return str(v)


class CTPMdSpi(ctp_md.CThostFtdcMdSpi):
    def __init__(self, api, params):
        super().__init__()
        self._api = api
        self._request_id = 0
        self.params = params
        self.BrokerID = params.get('BrokerID', "")
        self.UserID   = params.get('UserID', "")
        # 订阅合约列表
        self.Instruments = params.get('Instruments', [])

    def _next(self):
        self._request_id += 1
        return self._request_id

    # ============================================================
    # 连接 / 登录
    # ============================================================
    def OnFrontConnected(self):
        try:
            print(f"[OnFrontConnected行情连接] 前置机连接成功 交易日:{self._api.GetTradingDay()} API:{self._api.GetApiVersion()}")
            req = ctp_md.CThostFtdcReqUserLoginField()
            req.BrokerID = self.BrokerID
            req.UserID   = self.UserID
            ret = self._api.ReqUserLogin(req, self._next())
            print(f"[OnFrontConnected行情登录] ReqUserLogin发送登录请求 ret={ret}")
        except Exception:
            print("!!! OnFrontConnected 异常 !!!")
            traceback.print_exc()

    def OnFrontDisconnected(self, nReason):
        print(f"[OnFrontDisconnected行情连接] 前置机断开 nReason={nReason}")

    def OnHeartBeatWarning(self, nTimeLapse):
        print(f"[OnHeartBeatWarning行情心跳] 警告 距上次心跳{nTimeLapse}秒")

    def OnRspUserLogin(self, pRspUserLogin, pRspInfo, nRequestID, bIsLast):
        try:
            if pRspInfo is not None and pRspInfo.ErrorID != 0:
                print(f"[OnRspUserLogin行情登录] 失败 ErrorID={pRspInfo.ErrorID} "
                      f"ErrorMsg={pRspInfo.ErrorMsg}")
                return
            if pRspUserLogin is not None:
                print(f"[OnRspUserLogin行情登录] 成功 交易日:{pRspUserLogin.TradingDay} SessionID={pRspUserLogin.SessionID} FrontID={pRspUserLogin.FrontID}")
            else:
                print("[OnRspUserLogin行情登录] 成功（无登录字段）")

            # 登录成功后立即订阅
            self._subscribe(self.Instruments)
        except Exception:
            print("!!! OnRspUserLogin 异常 !!!")
            traceback.print_exc()

    def OnRspUserLogout(self, pUserLogout, pRspInfo, nRequestID, bIsLast):
        try:
            print(f"[OnRspUserLogout行情登出] BrokerID={getattr(pUserLogout, 'BrokerID', 'N/A')} UserID={getattr(pUserLogout, 'UserID', 'N/A')}")
        except Exception:
            traceback.print_exc()

    # ============================================================
    # 订阅
    # ============================================================
    def _subscribe(self, instruments):
        try:
            if not instruments:
                print("[订阅] 合约列表为空，跳过")
                return
            # SWIG 的 char ** typemap 要求 bytes 列表
            inst_bytes = [
                s.encode("ascii") if isinstance(s, str) else s
                for s in instruments
            ]
            ret = self._api.SubscribeMarketData(inst_bytes, len(inst_bytes))
            print(f"[SubscribeMarketData订阅] 请求订阅 {instruments} ret={ret}")
        except Exception:
            print("!!! _subscribe 异常 !!!")
            traceback.print_exc()

    def OnRspSubMarketData(self, pSpecificInstrument, pRspInfo, nRequestID, bIsLast):
        try:
            if pRspInfo is not None and pRspInfo.ErrorID != 0:
                print(f"[OnRspSubMarketData订阅] 失败 ErrorID={pRspInfo.ErrorID} ErrorMsg={pRspInfo.ErrorMsg}")
                return
            if pSpecificInstrument is not None:
                print(f"[OnRspSubMarketData订阅] 成功 InstrumentID={pSpecificInstrument.InstrumentID} bIsLast={bIsLast}")
            else:
                print(f"[OnRspSubMarketData订阅] 成功（无合约字段） bIsLast={bIsLast}")
        except Exception:
            print("!!! OnRspSubMarketData 异常 !!!")
            traceback.print_exc()

    def OnRspUnSubMarketData(self, pSpecificInstrument, pRspInfo, nRequestID, bIsLast):
        try:
            if pRspInfo is not None and pRspInfo.ErrorID != 0:
                print(f"[OnRspUnSubMarketData退订] 失败 ErrorID={pRspInfo.ErrorID} ErrorMsg={pRspInfo.ErrorMsg}")
                return
            if pSpecificInstrument is not None:
                print(f"[OnRspUnSubMarketData退订] 成功 InstrumentID={pSpecificInstrument.InstrumentID} bIsLast={bIsLast}")
        except Exception:
            print("!!! OnRspUnSubMarketData 异常 !!!")
            traceback.print_exc()

    def OnRspQryMulticastInstrument(self, pMulticastInstrument, pRspInfo, nRequestID, bIsLast):
        try:
            if pRspInfo is not None and pRspInfo.ErrorID != 0:
                print(f"[OnRspQryMulticastInstrument组播查询] 错误 ErrorID={pRspInfo.ErrorID} ErrorMsg={pRspInfo.ErrorMsg}")
                return
            if pMulticastInstrument is not None:
                m = pMulticastInstrument
                print(f"[OnRspQryMulticastInstrument组播查询] InstrumentID={m.InstrumentID} ExchangeID={getattr(m, 'ExchangeID', 'N/A')}")
        except Exception:
            print("!!! OnRspQryMulticastInstrument 异常 !!!")
            traceback.print_exc()

    def OnRspError(self, pRspInfo, nRequestID, bIsLast):
        try:
            if pRspInfo is not None:
                print(f"[OnRspError行情错误] ErrorID={pRspInfo.ErrorID} "
                      f"ErrorMsg={pRspInfo.ErrorMsg} "
                      f"nRequestID={nRequestID}")
        except Exception:
            traceback.print_exc()

    # ============================================================
    # 行情数据推送
    # ============================================================
    def OnRtnDepthMarketData(self, pDepthMarketData):
        try:
            if pDepthMarketData is None:
                return
            d = pDepthMarketData
            # 五档买卖盘拼成一行
            bid_lines = []
            ask_lines = []
            for i in range(1, 6):
                bp = getattr(d, f"BidPrice{i}", None)
                bv = getattr(d, f"BidVolume{i}", None)
                ap = getattr(d, f"AskPrice{i}", None)
                av = getattr(d, f"AskVolume{i}", None)
                if bp is not None and bp < _DBL_INVALID:
                    bid_lines.append(f"{_fd(bp)}x{bv}")
                if ap is not None and ap < _DBL_INVALID:
                    ask_lines.append(f"{_fd(ap)}x{av}")

            print(
                f"[OnRtnDepthMarketData行情推送] {d.ExchangeID} {d.InstrumentID} "
                f"时间={d.ActionDay} {d.UpdateTime}.{d.UpdateMillisec:03d} "
                f"交易日={d.TradingDay} "
                f"最新={_fd(d.LastPrice)} "
                f"开盘={_fd(d.OpenPrice)} "
                f"最高={_fd(d.HighestPrice)} "
                f"最低={_fd(d.LowestPrice)} "
                f"昨结={_fd(d.PreSettlementPrice)} "
                f"昨收={_fd(d.PreClosePrice)} "
                f"昨持仓={_fd(d.PreOpenInterest, 0)} "
                f"今开={_fd(d.OpenInterest, 0)} "
                f"成交量={d.Volume} 成交额={_fd(d.Turnover)} "
                f"均价={_fd(d.AveragePrice)} "
                f"涨停={_fd(d.UpperLimitPrice)} "
                f"跌停={_fd(d.LowerLimitPrice)} "
                f"买盘={' | '.join(bid_lines) if bid_lines else 'N/A'} "
                f"卖盘={' | '.join(ask_lines) if ask_lines else 'N/A'}"
            )
        except Exception:
            print("!!! OnRtnDepthMarketData 异常 !!!")
            traceback.print_exc()


# ============================================================
# 主流程
# ============================================================
if __name__ == "__main__":
    md_api = None
    try:
        md_params = dict()
        md_params['BrokerID'] = "9999"
        md_params['UserID'] = "188795"
        md_params['Instruments'] = ["IM2612", "IC2612", "IF2612", "IH2612"]
        
        md_api = ctp_md.CThostFtdcMdApi.CreateFtdcMdApi()
        md_spi = CTPMdSpi(api=md_api, params=md_params)
        # 注册回调类
        md_api.RegisterSpi(md_spi)
        # 注册前置
        md_api.RegisterFront("tcp://182.254.243.31:40011")
        # 登录前置
        md_api.Init()

        # 接收行情一段时间
        time.sleep(30)
    except BaseException:
        traceback.print_exc()
    finally:
        if md_api is not None:
            print("[主流程] 释放行情 API")
            md_api.Release()