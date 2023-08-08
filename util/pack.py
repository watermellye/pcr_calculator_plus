import re

class PackInvaildException(Exception):
    pass


class Pack():
    def __init__(self, D: int = None, T: int = None):
        """
        和出刀相关的数据。从字符串反序列化为标准化对象，以用于传入其余方法中。

        Args:
            D (int, optional): [boss当前血量](B) 或 [对boss造成的伤害](D). Defaults to 0.
            T (int, optional): [打死boss后剩余时间](T) 或 [期望返还时间](E). Defaults to 0.
        
        Raises:
            PackInvaildException
        """        
        self.D = D
        self.T = T
        self.verify()


    def verify(self) -> None:
        """
        判断实例对象的数据是否合法。
        如合法则无返回，任何非法将抛出异常。

        Raises:
            PackInvaildException
        """        
        if self.D is None and self.T is None:
            raise PackInvaildException("所有字段均为空")
        if self.D is not None:
            if self.D <= 0:
                raise PackInvaildException(f'字段[D]的值[{self.D}]非法')
        if self.T is not None:
            if not 0 < self.T <= 90:
                raise PackInvaildException(f'字段[T]的值[{self.T}]非法')

    def ToString(self) -> str:
        raise NotImplementedError("不应直接序列化基类")

    def __str__(self):
        return self.ToString()


    @classmethod
    def is_valid(cls, pack) -> bool:
        if cls == Pack:
            return True
        try:
            cls(pack)
        except PackInvaildException as e:
            return False
        return True


class PackB(Pack):
    def __init__(self, pack: Pack):
        self.name = "boss血量"
        super().__init__(pack.D, pack.T)
        self.verify()
        
        
    def verify(self) -> None:
        if self.D is None:
            raise PackInvaildException(f'[{self.name}]对象未提供字段[D]')
        if self.T is not None:
            raise PackInvaildException(f'[{self.name}]对象不应存在字段[T]，当前存在T=[{self.T}]')
    
    def ToString(self) -> str:
        outp = f'{self.D}' if self.D % 10000 else f'{self.D // 10000}w'
        return f'{self.name}={outp}'


class PackDT(Pack):
    def __init__(self, pack: Pack):
        self.name = "对boss伤害"
        super().__init__(pack.D, pack.T)
        self.verify()
        
        
    def verify(self) -> None:
        if self.T is not None:
            if self.T == 90:
                raise PackInvaildException(f'[{self.name}]对象的字段[T]=[{self.T}]非法')
    
    def ToString(self, b: PackB = None) -> str:
        if self.D is None and b is not None:
            self.D = b.D
        if self.D is None:
            outp = "击杀"
        elif self.D % 10000:
            outp = f'{self.D}'
        else:
            outp = f'{self.D // 10000}w'
        if self.T is not None:
            outp += f'余{self.T}s'
        return f'{self.name}={outp}'   


class PackE(Pack):
    def __init__(self, pack: Pack):
        self.name = "期望返还时间"
        super().__init__(pack.D, pack.T)
        self.verify()
        
        
    def verify(self) -> None:
        if self.T is None:
            raise PackInvaildException(f'[{self.name}]对象未提供字段[T]')
        if self.D is not None:
            raise PackInvaildException(f'[{self.name}]对象不应存在字段[D]，当前存在D=[{self.D}]')
        if self.T < 21:
            raise PackInvaildException(f'[{self.name}]对象的字段[T]不应小于21s，当前存在T=[{self.T}]')
    
    
    def ToString(self) -> str:
        return f'{self.name}={self.T}s'


def from_string(s: str) -> Pack:
    """
    将伤害从字符串反序列化为对象
    D可接受的格式: 1000 1000w 1000W 1000万 10000000 1500-500
    T可接受的格式：30 30s 30S 15+15
    T相当于B+T的缩写。例如：cal 700 30s == cal 700 700+30s
    当无量纲时，≥1w被识别为伤害，(90, 1w)被识别为伤害且自动×1w，≤90被识别为秒数
    如需同时传入D和T，应使用加号。举例：“800+55s”
    
    
    Args:
        s (str): 待解析字符串
    
    Raises:
        PackInvaildException

    Returns:
        package: 反序列化后的对象
    """        
    
    def auto_d(d: int) -> int:
        return d * 10000 if d < 10000 else d

    original_input = s
    s = re.sub(r'[wW万]', 'w', s)
    s = re.sub(r'[sS秒]', 's', s)


    # DT
    pattern = re.compile(r'^(\d+)\+(\d+)s$')
    match = pattern.fullmatch(s)
    if match:
        d = auto_d(int(match[1]))
        t = int(match[2])
        return Pack(d, t)

    # T
    if 's' in s:
        try:
            t = int(eval(s.replace('s', '')))
        except Exception as e:
            raise PackInvaildException(f'无法将[{original_input}]解析为时间')
        else:
            return Pack(T=t)

    # D
    if 'w' in s:
        try:
            d = int(eval(s.replace('w', '0000')))
        except Exception as e:
            raise PackInvaildException(f'无法将[{original_input}]解析为伤害')
        else:
            return Pack(D=auto_d(d))

    # 无量纲
    try:
        i = int(eval(s))
    except Exception as e:
        raise PackInvaildException(f'无法将[{original_input}]解析为伤害')
    else:
        return Pack(T=i) if i <= 90 else Pack(D=auto_d(i))


if __name__ == "__main__":
    # pack1 = from_string("700+123")
    # print(PackE.is_valid(pack1))
    
    # pack2 = from_string("30-13")
    # print(PackE.is_valid(pack2))
    
    try:
        pack = from_string("700+123")
        pack_b = PackB(pack)
    except PackInvaildException as e:
        print(f'Error: {e}')
    else:
        print(pack_b)
    