%module(directors="1") ctp_md
%{ 
#include "ThostFtdcMdApi.h"
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

%typemap(in) char *[] {
  if (!PyList_Check($input)) {
    PyErr_SetString(PyExc_TypeError, "not a list");
    SWIG_fail;
  }
  int size = PyList_Size($input);
  $1 = (char **) calloc((size + 1), sizeof(char *));
  if (!$1) {
    PyErr_NoMemory();
    SWIG_fail;
  }
  for (int i = 0; i < size; i++) {
    PyObject *o = PyList_GetItem($input, i);
    const char *s = NULL;
    if (PyUnicode_Check(o)) {
      s = PyUnicode_AsUTF8(o);          // Python 3 原生 API
    } else if (PyBytes_Check(o)) {
      s = PyBytes_AsString(o);          // 兼容直接传 bytes
    }
    if (!s) {
      for (int j = 0; j < i; j++) free($1[j]);
      free($1);
      PyErr_SetString(PyExc_TypeError, "list must contain strings");
      SWIG_fail;
    }
    $1[i] = strdup(s);                  // 复制，不能存 Python 内部缓冲指针
  }
  $1[size] = NULL;
}

%typemap(freearg) char ** {
  if ($1) {
    for (int i = 0; $1[i] != NULL; i++) free($1[i]);
    free($1);
  }
}
%feature("director") CThostFtdcMdSpi;
%ignore THOST_FTDC_VTC_BankBankToFuture;
%ignore THOST_FTDC_VTC_BankFutureToBank;
%ignore THOST_FTDC_VTC_FutureBankToFuture;
%ignore THOST_FTDC_VTC_FutureFutureToBank;
%ignore THOST_FTDC_FTC_BankLaunchBankToBroker;
%ignore THOST_FTDC_FTC_BrokerLaunchBankToBroker;
%ignore THOST_FTDC_FTC_BankLaunchBrokerToBank;
%ignore THOST_FTDC_FTC_BrokerLaunchBrokerToBank;
%warnfilter(514) CThostFtdcMdSpi;

%include "ThostFtdcUserApiDataType.h"
%include "ThostFtdcUserApiStruct.h"
%include "ThostFtdcMdApi.h"
