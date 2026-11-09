# -*- coding: utf-8 -*-
import ctp_wrap.ctp_td as ctp_td
import traceback
import time

# ============================================================
# 格式化辅助
# ============================================================
_DBL_INVALID = 1e300

def _fd(v, digits=2):
    """CTP 用 DBL_MAX 表示无效值，显示为 N/A"""
    if v is None:
        return "None"
    try:
        if v > _DBL_INVALID or v < -_DBL_INVALID:
            return "N/A"
        return f"{v:.{digits}f}"
    except Exception:
        return str(v)

def _fc(s):
    """取 char/char[N] 字段首字符，用于查枚举表"""
    try:
        return str(s)[:1]
    except Exception:
        return ""

_DIRECTION  = {"0": "买", "1": "卖"}
_OFFSET     = {"0": "开仓", "1": "平仓", "3": "平今", "4": "平昨"}
_POSI_DIR   = {"0": "净", "1": "多", "2": "空"}
_POSI_DATE  = {"1": "今仓", "2": "历史仓"}
_HEDGE      = {"1": "投机", "2": "套利", "3": "套保", "4": "做市商", "5": "备兑"}
_ORDER_STAT = {
    "0": "全部成交", "1": "部分成交还在队列中", "2": "部分成交不在队列中",
    "3": "未成交还在队列中", "4": "未成交不在队列中", "5": "撤单",
    "a": "未知", "b": "尚未触发", "c": "已触发",
}


class CTPTraderSpi(ctp_td.CThostFtdcTraderSpi):
    def __init__(self, api, params):
        super().__init__()
        self._api = api
        self._request_id = 0
        
        self._front_id   = None
        self._session_id = None
        self._order_ref  = 0  
        
        self.params = params
        self.ExchangeID = params.get('ExchangeID', "")
        self.BrokerID = params.get('BrokerID', "")
        self.Account  = params.get('Account', "")
        self.Password = params.get('Password', "")
        self.AppID    = params.get('AppID', "")
        self.AuthCode = params.get('AuthCode', "")

    def _next(self):
        self._request_id += 1
        return self._request_id

    # ============================================================
    # 主动请求
    # ============================================================
    def ReqQryFund(self):
        req = ctp_td.CThostFtdcQryTradingAccountField()
        req.BrokerID   = self.BrokerID
        req.InvestorID = self.Account
        ret = self._api.ReqQryTradingAccount(req, self._next())
        print(f"[ReqQryFund请求] 查询资金 ret={ret}")

    def ReqQryPosition(self):
        req = ctp_td.CThostFtdcQryInvestorPositionField()
        req.BrokerID   = self.BrokerID
        req.InvestorID = self.Account
        ret = self._api.ReqQryInvestorPosition(req, self._next())
        print(f"[ReqQryPosition请求] 查询持仓 ret={ret}")

    def ReqQryOrder(self):
        req = ctp_td.CThostFtdcQryOrderField()
        req.BrokerID   = self.BrokerID
        req.InvestorID = self.Account
        ret = self._api.ReqQryOrder(req, self._next())
        print(f"[ReqQryOrder请求] 查询订单 ret={ret}")

    def ReqQryTrade(self):
        req = ctp_td.CThostFtdcQryTradeField()
        req.BrokerID   = self.BrokerID
        req.InvestorID = self.Account
        ret = self._api.ReqQryTrade(req, self._next())
        print(f"[ReqQryTrade请求] 查询成交 ret={ret}")

    def ReqQryInstrument(self, exchange_id="", product_id=""):
        """
        请求查询合约。全部字段留空则查询所有合约。
        :param exchange_id: 可选，交易所代码（如 "SHFE"），留空查所有交易所
        :param product_id:  可选，品种代码（如 "rb"），留空查所有品种
        :return: ret
        """
        try:
            req = ctp_td.CThostFtdcQryInstrumentField()

            # 不赋值任何过滤字段 = 查询全部合约
            if exchange_id:
                req.ExchangeID = exchange_id
            if product_id:
                req.ProductID = product_id
            # InstrumentID 留空（SWIG 默认已初始化为空字符串）

            ret = self._api.ReqQryInstrument(req, self._next())
            scope = "全部合约"
            if exchange_id or product_id:
                scope = f"ExchangeID={exchange_id!r} ProductID={product_id!r}"
            print(f"[ReqQryInstrument请求] 查询合约 ({scope}) ret={ret}")
            return ret
        except Exception:
            print("!!! ReqQryInstrument 异常 !!!")
            traceback.print_exc()
            return -1
        
    def ReqQryInstrumentMarginRate(self, product_or_instrument=""):
        """
        请求查询合约保证金率。
        - 不传参数：返回当前持仓对应的合约保证金率（CTP 的填空语义，并非全市场）。
        - 传入品种代码（如 "rb"）：利用 6.7.11 特性，返回该品种下的保证金率数据。
        - 传入具体合约（如 "rb2501"）：返回该合约的保证金率。
        :param product_or_instrument: 品种代码或合约代码，留空则查持仓合约
        :return: ret
        """
        try:
            req = ctp_td.CThostFtdcQryInstrumentMarginRateField()
            req.BrokerID   = self.BrokerID
            req.InvestorID = self.Account

            if product_or_instrument:
                req.InstrumentID = product_or_instrument
                scope = f"InstrumentID={product_or_instrument!r}"
            else:
                # 留空：CTP 返回持仓合约的保证金率，不是全市场
                scope = "持仓合约（填空语义）"

            ret = self._api.ReqQryInstrumentMarginRate(req, self._next())
            print(f"[ReqQryInstrumentMarginRate请求] 查询保证金率 ({scope}) ret={ret}")
            if not product_or_instrument:
                print("注意:CTP 保证金率填空查询仅返回当前持仓合约，"
                    "无法一次获取全市场。如需按品种查询，请传入品种代码（如 'rb'）。")
            return ret
        except Exception:
            print("!!! ReqQryInstrumentMarginRate 异常 !!!")
            traceback.print_exc()
            return -1
        
    def ReqQryInstrumentCommissionRate(self, product_or_instrument=""):
        """
        请求查询合约手续费率。
        语义与保证金率查询一致：
        - 留空：返回持仓对应合约的手续费率。
        - 传入品种代码（如 "rb"）：返回该品种下的手续费率数据（6.7.11 特性）。
        - 传入具体合约：返回该合约的手续费率。
        :param product_or_instrument: 品种代码或合约代码，留空则查持仓合约
        :return: ret
        """
        try:
            req = ctp_td.CThostFtdcQryInstrumentCommissionRateField()
            req.BrokerID   = self.BrokerID
            req.InvestorID = self.Account

            if product_or_instrument:
                req.InstrumentID = product_or_instrument
                scope = f"InstrumentID={product_or_instrument!r}"
            else:
                scope = "持仓合约（填空语义）"

            ret = self._api.ReqQryInstrumentCommissionRate(req, self._next())
            print(f"[ReqQryInstrumentCommissionRate请求] 查询手续费率 ({scope}) ret={ret}")
            if not product_or_instrument:
                print("注意:CTP 手续费率填空查询仅返回当前持仓合约，"
                    "无法一次获取全市场。如需按品种查询，请传入品种代码（如 'rb'）。")
            return ret
        except Exception:
            print("!!! ReqQryInstrumentCommissionRate 异常 !!!")
            traceback.print_exc()
            return -1
    
    def ReqInsertOrder(self, symbol, direction, offset, price, volume):
        """
        限价报单。
        :param symbol:    合约代码，如 "rb2501"
        :param direction: 买卖方向，"0"=买，"1"=卖
        :param offset:    开平标志，"0"=开仓，"1"=平仓，"3"=平今（仅上期/能源）
        :param price:     限价，必须是 PriceTick 的整数倍
        :param volume:    手数，必须 > 0
        :return: (ret, order_ref)  ret=0 表示请求发送成功；order_ref 为本地生成的报单引用
        """
        try:
            self._order_ref += 1
            order_ref = str(self._order_ref)

            req = ctp_td.CThostFtdcInputOrderField()

            # ---- 账户与会话 ----
            req.BrokerID   = self.BrokerID
            req.InvestorID = self.Account
            req.UserID     = self.Account
            req.ExchangeID = self.ExchangeID

            # ---- 合约与方向 ----
            req.InstrumentID = symbol
            req.Direction    = direction                 # "0" 买 / "1" 卖

            # ---- 开平与投机套保 ----
            # CombOffsetFlag / CombHedgeFlag 是 char[5] 数组，用索引 [0] 设首元素
            req.CombOffsetFlag = offset               # "0" 开 / "1" 平 / "3" 平今
            req.CombHedgeFlag  = "1"                   # "1" 投机（SimNow 默认）

            # ---- 价格与数量 ----
            req.OrderPriceType     = "2"                  # "2" = 限价单
            req.LimitPrice         = price
            req.VolumeTotalOriginal = volume

            # ---- 有效期与成交条件 ----
            req.TimeCondition      = "3"                  # "3" = 当日有效（GFD）
            req.VolumeCondition    = "1"                  # "1" = 任何数量
            req.ContingentCondition = "1"                 # "1" = 立即
            req.MinVolume          = 1

            # ---- 报单引用（终端自行维护，会话内唯一）----
            req.OrderRef = order_ref
            
            req.ForceCloseReason    = "0"    # 非强平
            req.IsAutoSuspend       = 0      # 不自动挂起
            req.UserForceClose      = 0      # 非用户强平

            # ---- 发送 ----
            ret = self._api.ReqOrderInsert(req, self._next())
            if ret == 0:
                print(f"[ReqInsertOrder报单] 请求已发送 {symbol} 方向={direction} 开平={offset} "
                    f"价格={price} 手数={volume} OrderRef={order_ref}")
            else:
                print(f"[ReqInsertOrder报单] 发送失败 ret={ret} OrderRef={order_ref}")
            return ret, order_ref

        except Exception:
            print("!!! ReqInsertOrder 异常 !!!")
            traceback.print_exc()
            return -1, ""
    
    def ReqCancelOrder(self, symbol, orderref):
        """
        按 FrontID + SessionID + OrderRef 撤单。
        :param orderref: 报单时返回的 OrderRef 字符串
        :return: ret，0 表示请求发送成功
        """
        try:
            if self._front_id is None or self._session_id is None:
                print("[ReqCancelOrder撤单] 尚未登录或未获取 FrontID/SessionID，无法撤单")
                return -1

            req = ctp_td.CThostFtdcInputOrderActionField()

            # ---- 账户与会话 ----
            req.BrokerID   = self.BrokerID
            req.InvestorID = self.Account
            req.UserID     = self.Account
            req.ExchangeID = self.ExchangeID
            req.InstrumentID = symbol

            # ---- 报单定位三要素 ----
            req.FrontID   = self._front_id
            req.SessionID = self._session_id
            req.OrderRef  = str(orderref)

            # ---- 操作标志 ----
            req.ActionFlag = ctp_td.THOST_FTDC_AF_Delete          # "0" = THOST_FTDC_AF_Delete，删除/撤单

            ret = self._api.ReqOrderAction(req, self._next())
            if ret == 0:
                print(f"[ReqCancelOrder撤单] 请求已发送 {symbol} OrderRef={orderref} "
                    f"FrontID={self._front_id} SessionID={self._session_id}")
            else:
                print(f"[ReqCancelOrder撤单] 发送失败 {symbol} ret={ret} OrderRef={orderref}")
            return ret

        except Exception:
            print("!!! ReqCancelOrder 异常 !!!")
            traceback.print_exc()
            return -1
        
    # ============================================================
    # 连接 / 认证 / 登录 / 结算确认
    # ============================================================
    def OnFrontConnected(self):
        try:
            print(f"[OnFrontConnected连接] 交易前置机连接成功 交易日={self._api.GetTradingDay()} "
                  f"API={self._api.GetApiVersion()}")
            req_auth = ctp_td.CThostFtdcReqAuthenticateField()
            req_auth.BrokerID = self.BrokerID
            req_auth.UserID   = self.Account
            req_auth.AppID    = self.AppID
            req_auth.AuthCode = self.AuthCode
            ret = self._api.ReqAuthenticate(req_auth, self._next())
            print(f"[ReqAuthenticate认证] 发送认证请求 ret={ret}")
        except Exception:
            print("!!! OnFrontConnected 异常 !!!")
            traceback.print_exc()

    def OnFrontDisconnected(self, nReason):
        print(f"[OnFrontDisconnected连接] 交易前置机断开 nReason={nReason}")

    def OnRspAuthenticate(self, pRspAuthenticateField, pRspInfo, nRequestID, bIsLast):
        try:
            if pRspInfo is not None and pRspInfo.ErrorID != 0:
                print(f"[OnRspAuthenticate认证] 失败 ErrorID={pRspInfo.ErrorID} "
                      f"ErrorMsg={pRspInfo.ErrorMsg}")
                return
            print(f"[OnRspAuthenticate认证] 成功")
            login_req = ctp_td.CThostFtdcReqUserLoginField()
            login_req.BrokerID = self.BrokerID
            login_req.UserID   = self.Account
            login_req.Password = self.Password
            ret = self._api.ReqUserLogin(login_req, self._next())
            print(f"[ReqUserLogin登录] 发送登录请求 ret={ret}")
        except Exception:
            print("!!! OnRspAuthenticate 异常 !!!")
            traceback.print_exc()

    def OnRspUserLogin(self, pRspUserLogin, pRspInfo, nRequestID, bIsLast):
        try:
            if pRspInfo is not None and pRspInfo.ErrorID != 0:
                print(f"[OnRspUserLogin登录] 失败 ErrorID={pRspInfo.ErrorID} "
                      f"ErrorMsg={pRspInfo.ErrorMsg}")
                return
            if pRspUserLogin is not None:
                self._front_id   = pRspUserLogin.FrontID
                self._session_id = pRspUserLogin.SessionID
                self._order_ref = int(pRspUserLogin.MaxOrderRef) + 1
                print(f"[OnRspUserLogin登录] 成功 FrontID={self._front_id} SessionID={self._session_id} TradingDay={pRspUserLogin.TradingDay} "
                      f"MaxOrderRef={pRspUserLogin.MaxOrderRef}")
            else:
                print("[OnRspUserLogin登录] 成功（无登录字段）")
            req_confirm = ctp_td.CThostFtdcSettlementInfoConfirmField()
            req_confirm.BrokerID   = self.BrokerID
            req_confirm.InvestorID = self.Account
            ret = self._api.ReqSettlementInfoConfirm(req_confirm, self._next())
            print(f"[ReqSettlementInfoConfirm结算确认请求] 发送请求 ret={ret}")
        except Exception:
            print("!!! OnRspUserLogin 异常 !!!")
            traceback.print_exc()

    def OnRspSettlementInfoConfirm(self, pConfirm, pRspInfo, nRequestID, bIsLast):
        try:
            if pRspInfo is not None and pRspInfo.ErrorID != 0:
                print(f"[OnRspSettlementInfoConfirm结算确认] 失败 ErrorID={pRspInfo.ErrorID} "
                      f"ErrorMsg={pRspInfo.ErrorMsg}")
                return
            # ✅ 成功分支不再访问 pRspInfo.ErrorID（此时 pRspInfo 为 None）
            if pConfirm is not None:
                print(f"[OnRspSettlementInfoConfirm结算确认] 成功 BrokerID={pConfirm.BrokerID} "
                      f"InvestorID={pConfirm.InvestorID} "
                      f"ConfirmDate={pConfirm.ConfirmDate} bIsLast={bIsLast}")
            else:
                print(f"[OnRspSettlementInfoConfirm结算确认] 成功（无确认字段） bIsLast={bIsLast}")
        except Exception:
            print("!!! OnRspSettlementInfoConfirm 异常 !!!")
            traceback.print_exc()

    def OnRspUserLogout(self, pUserLogout, pRspInfo, nRequestID, bIsLast):
        try:
            print(f"[OnRspUserLogout登出] BrokerID={getattr(pUserLogout, 'BrokerID', 'N/A')} "
                  f"InvestorID={getattr(pUserLogout, 'InvestorID', 'N/A')}")
        except Exception:
            traceback.print_exc()

    # ============================================================
    # 资金、持仓、订单、成交查询响应
    # ============================================================
    def OnRspQryTradingAccount(self, pTradingAccount, pRspInfo, nRequestID, bIsLast):
        try:
            if pRspInfo is not None and pRspInfo.ErrorID != 0:
                print(f"[OnRspQryTradingAccount资金] 错误 ErrorID={pRspInfo.ErrorID} "
                      f"ErrorMsg={pRspInfo.ErrorMsg}")
                return
            if pTradingAccount is None:
                print(f"[OnRspQryTradingAccount资金] 无数据 bIsLast={bIsLast}")
                return
            ta = pTradingAccount
            print(
                f"[OnRspQryTradingAccount资金] AccountID={ta.AccountID} CurrencyID={ta.CurrencyID} "
                f"余额={_fd(ta.Balance)} 可用={_fd(ta.Available)} "
                f"可取={_fd(ta.WithdrawQuota)} "
                f"占用保证金={_fd(ta.CurrMargin)} "
                f"冻结保证金={_fd(ta.FrozenMargin)} "
                f"平仓盈亏={_fd(ta.CloseProfit)} "
                f"持仓盈亏={_fd(ta.PositionProfit)} "
                f"手续费={_fd(ta.Commission)} "
                f"入金={_fd(ta.Deposit)} 出金={_fd(ta.Withdraw)} "
                f"bIsLast={bIsLast}"
            )
        except Exception:
            print("!!! OnRspQryTradingAccount 异常 !!!")
            traceback.print_exc()

    def OnRspQryInvestorPosition(self, pInvestorPosition, pRspInfo, nRequestID, bIsLast):
        try:
            if pRspInfo is not None and pRspInfo.ErrorID != 0:
                print(f"[OnRspQryInvestorPosition持仓] 错误 ErrorID={pRspInfo.ErrorID} "
                      f"ErrorMsg={pRspInfo.ErrorMsg}")
                return
            if pInvestorPosition is None:
                print(f"[OnRspQryInvestorPosition持仓] 无数据 bIsLast={bIsLast}")
                return
            p = pInvestorPosition
            print(
                f"[OnRspQryInvestorPosition持仓] {p.ExchangeID} {p.InstrumentID} "
                f"方向={_POSI_DIR.get(p.PosiDirection, p.PosiDirection)} "
                f"日期={_POSI_DATE.get(_fc(p.PositionDate), p.PositionDate)} "
                f"总持仓={p.Position} 昨仓={p.YdPosition} "
                f"今仓={p.TodayPosition} "
                f"多头冻结={p.LongFrozen} 空头冻结={p.ShortFrozen} "
                f"开仓量={p.OpenVolume} 平仓量={p.CloseVolume} "
                f"开仓成本={_fd(p.OpenCost)} 占用保证金={_fd(p.UseMargin)} "
                f"持仓盈亏={_fd(p.PositionProfit)} "
                f"bIsLast={bIsLast}"
            )
        except Exception:
            print("!!! OnRspQryInvestorPosition 异常 !!!")
            traceback.print_exc()
            
    def OnRspQryOrder(self, pOrder, pRspInfo, nRequestID, bIsLast):
        try:
            if pRspInfo is not None and pRspInfo.ErrorID != 0:
                print(f"[OnRspQryOrder订单] 错误 ErrorID={pRspInfo.ErrorID} "
                      f"ErrorMsg={pRspInfo.ErrorMsg}")
                return
            if pOrder is None:
                print(f"[OnRspQryOrder订单] 无数据 bIsLast={bIsLast}")
                return
            o = pOrder
            print(
                f"[OnRspQryOrder订单] {o.ExchangeID} {o.InstrumentID} "
                f"OrderRef={o.OrderRef} OrderSysID={o.OrderSysID} "
                f"方向={_DIRECTION.get(_fc(o.Direction), o.Direction)} "
                f"开平={_OFFSET.get(_fc(o.CombOffsetFlag), o.CombOffsetFlag)} "
                f"价格={_fd(o.LimitPrice)} "
                f"委托={o.VolumeTotalOriginal} 已成交={o.VolumeTraded} "
                f"剩余={o.VolumeTotal} "
                f"状态={_ORDER_STAT.get(_fc(o.OrderStatus), o.OrderStatus)} "
                f"时间={o.InsertDate} {o.InsertTime} bIsLast={bIsLast}"
            )
        except Exception:
            print("!!! OnRspQryOrder 异常 !!!")
            traceback.print_exc()

    def OnRspQryTrade(self, pTrade, pRspInfo, nRequestID, bIsLast):
        try:
            if pRspInfo is not None and pRspInfo.ErrorID != 0:
                print(f"[OnRspQryTrade成交] 错误 ErrorID={pRspInfo.ErrorID} "
                      f"ErrorMsg={pRspInfo.ErrorMsg}")
                return
            if pTrade is None:
                print(f"[OnRspQryTrade成交] 无数据 bIsLast={bIsLast}")
                return
            t = pTrade
            print(
                f"[OnRspQryTrade成交] {t.ExchangeID} {t.InstrumentID} "
                f"TradeID={t.TradeID} OrderRef={t.OrderRef} "
                f"OrderSysID={t.OrderSysID} "
                f"方向={_DIRECTION.get(_fc(t.Direction), t.Direction)} "
                f"开平={_OFFSET.get(_fc(t.OffsetFlag), t.OffsetFlag)} "
                f"价格={_fd(t.Price)} 手数={t.Volume} "
                f"时间={t.TradeDate} {t.TradeTime} bIsLast={bIsLast}"
            )
        except Exception:
            print("!!! OnRspQryTrade 异常 !!!")
            traceback.print_exc()

    # ============================================================
    # 报单 / 撤单 响应
    # ============================================================
    def OnRspOrderInsert(self, pInputOrder, pRspInfo, nRequestID, bIsLast):
        try:
            if pRspInfo is not None and pRspInfo.ErrorID != 0:
                print(f"[OnRspOrderInsert报单] 失败 InstrumentID={pInputOrder.InstrumentID} OrderRef={pInputOrder.OrderRef} ErrorID={pRspInfo.ErrorID} "
                      f"ErrorMsg={pRspInfo.ErrorMsg}")
                return
            if pInputOrder is not None:
                o = pInputOrder
                print(f"[OnRspOrderInsert报单] 成功 {o.InstrumentID} "
                      f"方向={_DIRECTION.get(_fc(o.Direction), o.Direction)} "
                      f"开平={_OFFSET.get(_fc(o.CombOffsetFlag), o.CombOffsetFlag)} "
                      f"价格={_fd(o.LimitPrice)} 手数={o.VolumeTotalOriginal} "
                      f"OrderRef={o.OrderRef}")
            else:
                print("[OnRspOrderInsert报单] 成功（无输入包）")
        except Exception:
            print("!!! OnRspOrderInsert 异常 !!!")
            traceback.print_exc()

    def OnErrRtnOrderInsert(self, pInputOrder, pRspInfo):
        try:
            if pRspInfo is not None and pRspInfo.ErrorID != 0:
                print(f"[OnErrRtnOrderInsert报单错误回报] {pInputOrder.InstrumentID} {pInputOrder.OrderRef} ErrorID={pRspInfo.ErrorID} "
                      f"ErrorMsg={pRspInfo.ErrorMsg}")
        except Exception:
            traceback.print_exc()

    def OnRspOrderAction(self, pInputOrderAction, pRspInfo, nRequestID, bIsLast):
        try:
            if pRspInfo is not None and pRspInfo.ErrorID != 0:
                print(f"[OnRspOrderAction撤单] 失败 {pInputOrderAction.OrderRef} ErrorID={pRspInfo.ErrorID} "
                      f"ErrorMsg={pRspInfo.ErrorMsg}")
            else:
                print("[OnRspOrderAction撤单] 成功")
        except Exception:
            traceback.print_exc()

    def OnErrRtnOrderAction(self, pOrderAction, pRspInfo):
        try:
            if pRspInfo is not None and pRspInfo.ErrorID != 0:
                print(f"[OnErrRtnOrderAction撤单错误回报] {pOrderAction.OrderRef} ErrorID={pRspInfo.ErrorID} "
                      f"ErrorMsg={pRspInfo.ErrorMsg}")
        except Exception:
            traceback.print_exc()

    # ============================================================
    # 实时回报
    # ============================================================
    def OnRtnOrder(self, pOrder):
        try:
            if pOrder is None:
                return
            o = pOrder
            print(
                f"[OnRtnOrder订单回报] {o.ExchangeID} {o.InstrumentID} "
                f"OrderRef={o.OrderRef} OrderSysID={o.OrderSysID} "
                f"方向={_DIRECTION.get(_fc(o.Direction), o.Direction)} "
                f"开平={_OFFSET.get(_fc(o.CombOffsetFlag), o.CombOffsetFlag)} "
                f"价格={_fd(o.LimitPrice)} "
                f"成交={o.VolumeTraded}/{o.VolumeTotalOriginal} "
                f"状态={_ORDER_STAT.get(_fc(o.OrderStatus), o.OrderStatus)} "
                f"时间={o.InsertDate} {o.InsertTime}"
            )
        except Exception:
            print("!!! OnRtnOrder 异常 !!!")
            traceback.print_exc()

    def OnRtnTrade(self, pTrade):
        """成交回报——原代码误用 pOrder 会导致 NameError 崩溃"""
        try:
            if pTrade is None:
                return
            t = pTrade
            print(
                f"[OnRtnTrade成交回报] {t.ExchangeID} {t.InstrumentID} "
                f"TradeID={t.TradeID} OrderRef={t.OrderRef} "
                f"方向={_DIRECTION.get(_fc(t.Direction), t.Direction)} "
                f"开平={_OFFSET.get(_fc(t.OffsetFlag), t.OffsetFlag)} "
                f"价格={_fd(t.Price)} 手数={t.Volume} "
                f"时间={t.TradeDate} {t.TradeTime}"
            )
        except Exception:
            print("!!! OnRtnTrade 异常 !!!")
            traceback.print_exc()

    # ============================================================
    # 合约 / 保证金率 / 手续费率
    # ============================================================
    def OnRspQryInstrument(self, pInstrument, pRspInfo, nRequestID, bIsLast):
        try:
            if pRspInfo is not None and pRspInfo.ErrorID != 0:
                print(f"[OnRspQryInstrument合约] 错误 ErrorID={pRspInfo.ErrorID} "
                      f"ErrorMsg={pRspInfo.ErrorMsg}")
                return
            if pInstrument is not None:
                i = pInstrument
                print(f"[OnRspQryInstrument合约] {i.ExchangeID} {i.InstrumentID} "
                      f"名称={i.InstrumentName} 品种={i.ProductID} "
                      f"乘数={i.VolumeMultiple} "
                      f"最小变动={_fd(i.PriceTick, 4)} 可交易={i.IsTrading}")
            if bIsLast:
                print("[OnRspQryInstrument合约] 查询结束")
        except Exception:
            print("!!! OnRspQryInstrument 异常 !!!")
            traceback.print_exc()
            
    def OnRspQryInstrumentMarginRate(self, pInstrumentMarginRate, pRspInfo, nRequestID, bIsLast):
        try:
            if pRspInfo is not None and pRspInfo.ErrorID != 0:
                print(f"[OnRspQryInstrumentMarginRate保证金率] 错误 ErrorID={pRspInfo.ErrorID} "
                      f"ErrorMsg={pRspInfo.ErrorMsg}")
                return
            if pInstrumentMarginRate is not None:
                m = pInstrumentMarginRate
                print(f"[OnRspQryInstrumentMarginRate保证金率] {m.ExchangeID} {m.InstrumentID} "
                      f"投保={_HEDGE.get(_fc(m.HedgeFlag), m.HedgeFlag)} "
                      f"多头={_fd(m.LongMarginRatioByMoney, 4)} "
                      f"空头={_fd(m.ShortMarginRatioByMoney, 4)} bIsLast={bIsLast}")
        except Exception:
            print("!!! OnRspQryInstrumentMarginRate 异常 !!!")
            traceback.print_exc()

    def OnRspQryInstrumentCommissionRate(self, pInstrumentCommissionRate, pRspInfo, nRequestID, bIsLast):
        try:
            if pRspInfo is not None and pRspInfo.ErrorID != 0:
                print(f"[OnRspQryInstrumentCommissionRate手续费率] 错误 ErrorID={pRspInfo.ErrorID} "
                      f"ErrorMsg={pRspInfo.ErrorMsg}")
                return
            if pInstrumentCommissionRate is not None:
                c = pInstrumentCommissionRate
                print(f"[OnRspQryInstrumentCommissionRate手续费率] {c.ExchangeID} {c.InstrumentID} "
                      f"开仓按值={_fd(c.OpenRatioByMoney, 6)} "
                      f"开仓按手={_fd(c.OpenRatioByVolume, 4)} "
                      f"平仓按值={_fd(c.CloseRatioByMoney, 6)} "
                      f"平仓按手={_fd(c.CloseRatioByVolume, 4)} "
                      f"bIsLast={bIsLast}")
        except Exception:
            print("!!! OnRspQryInstrumentCommissionRate 异常 !!!")
            traceback.print_exc()


# ============================================================
# 主流程
# ============================================================
if __name__ == "__main__":
    try:
        trader_params = dict()
        trader_params['ExchangeID'] = "CFFEX"
        trader_params['BrokerID'] = "9999"
        trader_params['Account'] = "188795"
        trader_params['Password'] = "XXXXXX"
        trader_params['AppID'] = "simnow_client_test"
        trader_params['AuthCode'] = "0000000000000000"
        
        td_api = ctp_td.CThostFtdcTraderApi.CreateFtdcTraderApi()
        td_spi = CTPTraderSpi(api=td_api, params=trader_params)
        td_api.RegisterSpi(td_spi)
        td_api.SubscribePublicTopic(ctp_td.THOST_TERT_RESTART)
        td_api.SubscribePrivateTopic(ctp_td.THOST_TERT_RESTART)
        td_api.RegisterFront("tcp://182.254.243.31:40001")
        td_api.Init()
        time.sleep(5)
        # 查询资金
        td_spi.ReqQryFund()
        time.sleep(5)
        # 查询持仓
        td_spi.ReqQryPosition()
        time.sleep(5)
        # 查询订单
        td_spi.ReqQryOrder()
        time.sleep(5)
        # 查询成交
        td_spi.ReqQryTrade()
        time.sleep(5)
        # 查询合约
        td_spi.ReqQryInstrument(exchange_id='CFFEX', product_id='IM')
        time.sleep(5)
        # 查询合约手续费
        td_spi.ReqQryInstrumentCommissionRate(product_or_instrument='IM')
        time.sleep(5)
        # 查询合约保证金率
        td_spi.ReqQryInstrumentMarginRate(product_or_instrument='IM')
        time.sleep(5)
        # 发送订单测试
        ret, order_ref = td_spi.ReqInsertOrder(symbol="IM2612", direction="0", offset="0", price=6000.0, volume=1)
        time.sleep(5)
        # 发送撤单测试
        if order_ref:
            ret = td_spi.ReqCancelOrder(symbol="IM2612", orderref=order_ref)
            time.sleep(5)
        time.sleep(10)
    except BaseException:
        traceback.print_exc()
    finally:
        if td_api is not None:
            print("[主流程] 释放行情 API")
            td_api.Release()