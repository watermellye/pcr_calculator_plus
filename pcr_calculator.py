# python base
from pathlib import Path
from typing import Union, List
import math
# from pip
from sympy import symbols, Eq, solve, parse_expr
from nonebot import Message, MessageSegment
# from project root
from hoshino import Service
from hoshino.typing import CQEvent, HoshinoBot
# relative
from .util.output import *
from .util.pack import *

gs_current_dir = Path(__file__).parent
sv = Service('pcr_calculator')

async def send_help(bot: HoshinoBot, ev: CQEvent):
    await bot.send(ev, MessageSegment.image(f'file:///{gs_current_dir / "data" / "help.png"}'))


@sv.on_prefix(['尾刀计算', 'cal', '合刀'])
async def pcr_calculator_interface(bot: HoshinoBot, ev: CQEvent):
    msg = ev.message.extract_plain_text().strip()
    if len(msg) == 0:
        await send_help(bot, ev)
        return
    await bot.send(ev, pcr_calculator(msg).ToString(sep="\n\n"))


def try_prase(raw_packs:List[Pack], pack_types: str) -> Union[list, None]:
    pack_types = pack_types.upper().split('_')
    assert len(raw_packs) == len(pack_types), f'Internal Error: len(packs)[{len(raw_packs)}] != len(pack_types)[{len(pack_types)}]\npack_types={pack_types}'
    outp = []
    for raw_pack, pack_type in zip(raw_packs, pack_types):
        if pack_type == "B":
            try:
                outp.append(PackB(raw_pack))
            except PackInvaildException as e:
                return None
        elif pack_type == "E":
            try:
                outp.append(PackE(raw_pack))
            except PackInvaildException as e:
                return None
        elif pack_type == "DT":
            try:
                outp.append(PackDT(raw_pack))
            except PackInvaildException as e:
                return None
        else:
            raise AssertionError(f'Internal Error: invaild pack_type [{pack_type}]')
    return outp


delta = 0.00001


def solve_equation(e, b, d, t = 0) -> Union[int, None]:
    """
    计算方程[e=110-(90-t)/(d/b)]的结果。
    [补偿秒数e] = min(90, math.ceil(110 - (90-[剩余秒数t])/([造成伤害d]/[boss血量b])))
    
    公式解释：（可以不看）
    [90-t]==[你实际使用的秒数(设为y)]。
    公式的内生逻辑在于，你对boss造成了[d/b(设为x)]倍于boss的伤害，
    则认为你实际只需要y/x的时间即可对boss造成d的伤害
    所以返还你[90-y/x](=90-(90-t)/(d/b))秒的时间，再额外奖励20s，再向上取整，即获得上述方程。

    Args:
        e: 期望获得时间
        b: boss血量
        d: 造成伤害
        t (optional): 剩余秒数. Defaults to 0.

    Returns:
        Union[int, None]: 有解则返回解的向上取整结果，否则返回None
    """    
  
    _e, _b, _d, _t, x = symbols('e b d t x')

    e_x = Eq(_e, parse_expr(str(e)))
    b_x = Eq(_b, parse_expr(str(b)))
    d_x = Eq(_d, parse_expr(str(d)))
    t_x = Eq(_t, parse_expr(str(t)))

    eqn = Eq(_e, 110 - (90 - _t) * _b / _d).subs({_e: e_x.rhs, _b: b_x.rhs, _d: d_x.rhs, _t: t_x.rhs})
    res = [int(math.ceil(res.evalf())) for res in solve(eqn, x) if res.is_real]
    return res[0] if len(res) else None

        
def B(raw_packs: List[Pack]) -> Output:
    pack_types = "B"
    def _(b: PackB) -> Output:
        output = [str(b), "刀数 / 满补所需伤害"]
        for i in range(1, 4 + 1):
            output.append(f"{i}刀 \t {solve_equation(89+delta, f'{b.D}-{i-1}*x', 'x')}")
        return Output(OutputFlag.Succeed, "\n".join(output))

    packs = try_prase(raw_packs, pack_types)
    return Output() if packs is None else _(*packs)


def B_DT(raw_packs: List[Pack]) -> Output:
    pack_types = "B_DT"
    def _(b: PackB, dt: PackDT) -> Output:
        output = [str(b), str(dt)]
        if dt.T is None: # B_D
            if b.D > dt.D: # cal 700 400
                另一刀后出 = solve_equation(89+delta, b.D-dt.D, 'x')
                if 另一刀后出 >= b.D:
                    output.append(f'若{dt.D // 10000}w先出，后出刀需{另一刀后出}伤害（高于boss血量）才能满补')
                else:
                    output.append(f'若{dt.D // 10000}w先出，后出刀需{另一刀后出}伤害可满补')
                另一刀先出 = solve_equation(89+delta, f'{b.D}-x', dt.D)
                output.append(f'若{dt.D // 10000}w后出，先出刀需{另一刀先出}伤害可满补')
            else: # cal 400 700
                e = min(solve_equation('x', b.D, dt.D), 90)
                output.append(f'补偿{e}s')
                if e < 90:
                    output.append(f"垫入{solve_equation(89+delta, f'{b.D}-x', dt.D)}伤害可满补")            
        else: # B_T B_DT
            if dt.D is None: # B_T
                dt.D = b.D
                output = [str(b), str(dt)]
            
            if b.D > dt.D:
                return Output(OutputFlag.Error, f'参数不合法：boss血量[{b.D}]高于尾刀伤害[{dt.D}余{dt.T}s]')
            
            返还 = min(90, solve_equation('x', b.D, dt.D, dt.T))
            使用 = 90 - dt.T
            output.append(f'使用了{使用}s，返还{返还}s')
                
            if 返还 < 90:
                if dt.D == b.D:
                    一穿二 = 使用 + 1
                    if 返还 >= 一穿二:
                        output.append(f'需返还{一穿二}s以一穿二，当前已足够')
                    else:
                        output.append(f"需返还{一穿二}s以一穿二，还需垫入{solve_equation(使用+delta, f'{b.D}-x', dt.D, dt.T)}伤害")
                output.append(f"垫入{solve_equation(89+delta, f'{b.D}-x', dt.D, dt.T)}伤害可满补")
                
            
        return Output(OutputFlag.Succeed, "\n".join(output))

    packs = try_prase(raw_packs, pack_types)
    return Output() if packs is None else _(*packs)


def B_E(raw_packs: List[Pack]) -> Output:
    pack_types = "B_E"
    def _(b: PackB, e: PackE) -> Output:        
        output = [str(b), str(e), "刀数 / 所需伤害"]
        for i in range(1, 3 + 1):
            output.append(f"{i}刀 \t {solve_equation(e.T-1+delta, f'{b.D}-{i-1}*x', 'x')}")
        return Output(OutputFlag.Succeed, "\n".join(output))

    packs = try_prase(raw_packs, pack_types)
    return Output() if packs is None else _(*packs)


def B_DT_DT(raw_packs: List[Pack]) -> Output:
    pack_types = "B_DT_DT"
    def _(b: PackB, dt1: PackDT, dt2: PackDT) -> Output:
        if dt1.T is not None and dt2.T is not None:
            return Output()
        if dt1.T is None and dt2.T is None: # B_D_D
            ds = min(dt1.D, dt2.D)
            db = max(dt1.D, dt2.D)
            
            output = [str(b), f'{dt1} | {str(dt2).split("=")[1]}']
            if ds >= b.D:
                output.append("两刀均斩杀boss，无法合刀，请检查输入")
            elif ds + db < b.D:
                output.append(f'剩余{b.D-ds-db}血')
            else:
                ds先出 = min(90, solve_equation("x", b.D-ds, db))
                db先出 = min(90, solve_equation("x", b.D-db, ds))
                if db < b.D:
                    if ds先出 == db先出:
                        output.append(f'无论哪刀先出，均补偿{ds先出}s')
                    else:
                        output.append(f'若[{ds}]先出，[{db}]后出，补偿{ds先出}s')
                        output.append(f'若[{db}]先出，[{ds}]后出，补偿{db先出}s')
                else:
                    output.append(f'若[{ds}]先出，[{db}]后出，补偿{ds先出}s')
                    output.append(f'若[{db}]直出，不出[{ds}]，补偿{db先出}s')
        else: # B_D_T B_T_D B_D_DT B_DT_D
            if dt2.T is None:
                dt1, dt2 = dt2, dt1 # B_D_T B_D_DT
            d, dt = dt1, dt2
            if dt.D is None:
                dt.D = b.D
            output = [str(b), f'{dt1} | {str(dt2).split("=")[1]}']
            if d.D >= b.D:
                return Output()
            elif dt.D < b.D:
                output.append("参数不合法：boss血量高于尾刀伤害")
            else:
                ds先出 = min(90, solve_equation("x", b.D-d.D, dt.D, dt.T))
                db直出 = min(90, solve_equation("x", b.D, dt.D, dt.T))
                if db直出 == 90:
                    output.append(f'[{dt.D}+{dt.T}s]直出已可满补，[{d.D}]不用出')
                else:
                    output.append(f'若[{d.D}]先出，[{dt.D}+{dt.T}s]后出，补偿{ds先出}s')
                    output.append(f'若[{dt.D}+{dt.T}s]直出，不出[{d.D}]，补偿{db直出}s')
        
        return Output(OutputFlag.Succeed, "\n".join(output))

    packs = try_prase(raw_packs, pack_types)
    return Output() if packs is None else _(*packs)


def B_DT_E(raw_packs: List[Pack]) -> Output:
    pack_types = "B_DT_E"
    def _(b: PackB, dt: PackDT, e: PackE) -> Output:
        if dt.D is None:
            dt.D = b.D
        if dt.T is not None and dt.D < b.D:
            return Output(OutputFlag.Error, f'参数不合法：boss血量[{b.D}]高于尾刀伤害[{dt.D}余{dt.T}s]')
        if dt.D >= b.D:
            返还 = min(90, solve_equation("x", b.D, dt.D, dt.T or 0))
            output = [str(b), f"{dt} (返还{返还}s)"]
            if 返还 >= e.T:
                output.append(f'{e}, 已满足')
            else:
                output.append(f'{e}, 还需垫入{solve_equation(e.T-1+delta, f"{b.D}-x", dt.D, dt.T or 0)}伤害')
        else:
            output = [str(b), str(dt), str(e)]
            output.append(f'若{dt.D}后出，需先垫入{solve_equation(e.T-1+delta, f"{b.D}-x", dt.D)}伤害')
            output.append(f'若{dt.D}先出，需再接上{solve_equation(e.T-1+delta, b.D - dt.D, "x")}伤害')
            
        return Output(OutputFlag.Succeed, "\n".join(output))

    packs = try_prase(raw_packs, pack_types)
    return Output() if packs is None else _(*packs)


def pcr_calculator(s: str) -> Outputs:
    packs:List[Pack] = []
    for raw_pack in s.split():
        try:
            packs.append(from_string(raw_pack))
        except PackInvaildException as e:
            return Outputs.FromStr(OutputFlag.Error, f'无法解析[{raw_pack}]: {e}')
    outputs = Outputs(showFlag=False)
    if len(packs) == 1:
        outputs += B(packs)
    elif len(packs) == 2:
        outputs += B_DT(packs)
        outputs += B_E(packs) # 真没用吧
    elif len(packs) == 3:
        outputs += B_DT_DT(packs)
        outputs += B_DT_E(packs)
    else: # >= 4
        outputs.append(OutputFlag.Info, '''参数过多，请使用四则运算缩减参数\n
例：boss血量1000w，当前有一刀750w，一刀700w，求再垫入多少伤害可以获得85s补偿：\n
cal 1000-750 700 85s'''.strip())
    return outputs


def test(s: str) -> None:
    print(f'\nINPUT=[{s}]')
    print(pcr_calculator(s).ToString(sep="\n\n"))


gs_test = False
if gs_test:
    ...
    
    # # Wrong
    # test("0")
    # test("700 0")
    # test("700 0w")

    # # B
    # test("1500") 

    # # B_D
    # test("700 400")
    # test("700 650")
    # test("400 400")
    # test("400 700")
    # test("400 40000000")

    # # B_T
    # test("700 1s")
    # test("700 36s")
    # test("700 35s")
    # test("700 89s")
    # test("700 90s")
    # test("700 69s")
    # test("700 70s")

    # # B_DT
    # test("800 700+35s")
    # test("700 700+35s")
    # test("700 800+55s")

    # # B_D_D
    # test("700 200 300")
    # test("700 300 400")
    # test("700 698 699")
    # test("700 300 800")
    # test("700 800 900")
    # test("700 300 80000000")

    # # B_D_T
    # test("700 300 30s")
    # test("700 300 80s")
    # test("700 800 80s")

    # # B_D_DT
    # test("700 300 800+30s")
    # test("700 300 800+70s")
    # test("800 300 700+30s")

    # # B_D_E
    # test("700 900 80s")
    # test("700 900 90s")
    # test("700 1700 30s")
    # test("700 70000000 90s")
    # test("700 600 30s")
    # test("700 400 30s")
    # test("700 100 30s")

    # # B_T_E
    # test("700 10s 25s")
    # test("700 10s 30s")
    # test("700 10s 50s")
    # test("700 10s 90s")

    # # B_DT_E
    # test("800 700+10s 30s")
    # test("700 800+10s 30s")
    # test("700 800+10s 50s")
    # test("700 800+10s 90s")
    # test("700 80000000+10s 90s")

    # import sys
    # sys.exit(0)