from suds.transport.http import HttpTransport
from suds.transport.https import WindowsHttpAuthenticated


class NTLMSSPAuthenticated(WindowsHttpAuthenticated):
    """
    Provides Windows (NTLM) http authentication.
    @ivar pm: The password manager.
    @ivar handler: The authentication handler.
    """

    def u2handlers(self):
         # try to import ntlm support
        try:
            from ntlm3 import HTTPNtlmAuthHandler
        except ImportError:
            raise Exception("Cannot import python-ntlm3 module")
        handlers = HttpTransport.u2handlers(self)
        handlers.append(HTTPNtlmAuthHandler.HTTPNtlmAuthHandler(
            password_mgr=self.pm,header='Negotiate')
        )
        return handlers