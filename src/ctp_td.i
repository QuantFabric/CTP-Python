%module(directors="1") ctp_td

%{
#include "ThostFtdcTraderApi.h"
#include <codecvt>
#include <locale>
#include <vector>
#include <string>
using namespace std;
#ifdef _MSC_VER
const static locale g_loc("zh-CN");
#else
const static locale g_loc("zh_CN.GB18030");
#endif
%}

/* ---------- GBK → UTF-8：所有 char[] 字段返回时统一转换 ---------- */
%typemap(out) char[ANY], char[] {
    const std::string &gb2312($1);
    std::vector<wchar_t> wstr(gb2312.size());
    wchar_t* wstrEnd = nullptr;
    const char* gbEnd = nullptr;
    mbstate_t state = {};
    int res = use_facet<codecvt<wchar_t, char, mbstate_t> >
        (g_loc).in(state,
            gb2312.data(), gb2312.data() + gb2312.size(), gbEnd,
            wstr.data(), wstr.data() + wstr.size(), wstrEnd);

    if (codecvt_base::ok == res)
    {
        wstring_convert<codecvt_utf8<wchar_t>> cutf8;
        std::string result = cutf8.to_bytes(wstring(wstr.data(), wstrEnd));
        resultobj = SWIG_FromCharPtrAndSize(result.c_str(), result.size());
    }
    else
    {
        std::string result;
        resultobj = SWIG_FromCharPtrAndSize(result.c_str(), result.size());
    }
}

/* ---------- Director 防护：Python 回调异常不再 Abort ---------- */
%feature("director") CThostFtdcTraderSpi;

%feature("director:except") {
    if ($error != NULL) {
        PyErr_Print();                       // 先把 Python traceback 打到 stderr
        throw Swig::DirectorMethodException();
    }
}

%exception {
    try {
        $action
    } catch (Swig::DirectorException &e) {
        SWIG_fail;                           // 转回 Python 异常，安全返回
    }
}

/* ---------- 屏蔽 CTP 银期转账宏：避免 SWIG 解析告警 ---------- */
%ignore THOST_FTDC_VTC_BankBankToFuture;
%ignore THOST_FTDC_VTC_BankFutureToBank;
%ignore THOST_FTDC_VTC_FutureBankToFuture;
%ignore THOST_FTDC_VTC_FutureFutureToBank;
%ignore THOST_FTDC_FTC_BankLaunchBankToBroker;
%ignore THOST_FTDC_FTC_BrokerLaunchBankToBroker;
%ignore THOST_FTDC_FTC_BankLaunchBrokerToBank;
%ignore THOST_FTDC_FTC_BrokerLaunchBrokerToBank;

/* ---------- 屏蔽 SPI 无虚析构告警 ---------- */
%warnfilter(514) CThostFtdcTraderSpi;

/* ---------- 解析 CTP 头文件 ---------- */
%include "ThostFtdcUserApiDataType.h"
%include "ThostFtdcUserApiStruct.h"
%include "ThostFtdcTraderApi.h"