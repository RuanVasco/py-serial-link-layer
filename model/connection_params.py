class ConnectionParams():
    def __init__(self, timeout, max_retries, data_size):
        self.timeout = timeout
        self.max_retries = max_retries
        self.data_size = data_size