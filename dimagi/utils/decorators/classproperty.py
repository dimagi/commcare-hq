class classproperty(property):
    def __get__(self, cls, owner):
        return self.fget.__get__(None, owner)()