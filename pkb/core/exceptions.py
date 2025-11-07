class PKBException(Exception):
    """Base exception for PKB errors."""

    pass


class StateStoreException(PKBException):
    """Exception raised for state store errors."""

    pass


class DataSourceException(PKBException):
    """Exception raised for data source errors."""

    pass


class SearchBackendException(PKBException):
    """Exception raised for search backend errors."""

    pass


class ConfigurationException(PKBException):
    """Exception raised for configuration errors."""

    pass
