from pyomo.environ import *
import numpy as np

# Modelo
model = AbstractModel()

# Índices y Conjuntos
model.I = RangeSet(1, 6)
model.T = RangeSet(1, 12)

# Parámetros
model.c = Param(model.I, default=0, domain=NonNegativeReals)  # Costos
model.k = Param(model.T, model.I, default=0, domain=NonNegativeIntegers)  # Consumos
model.P0 = Param(model.I, default=0, domain=NonNegativeReals)  # Potencias iniciales por tramo
model.ce = Param(initialize=10.93) #coste fijo de enganche  (euros)
model.cv = Param(initialize=9.69) #coste fijo de verificacion (euros)
model.cda = Param(initialize=23.84) #coste variable de acceso (euros/kW) 
model.cde = Param(initialize=21.02) #coste variable de extension (euros/kW)
model.N = Param(initialize=2)   #numero de cambios máximos permitidos por año
model.M = Param(initialize=10000)  # Big M

# Variables
model.P = Var(model.I, model.T, domain=NonNegativeIntegers)  # Potencias asignadas por tramo y periodo
model.HU = Var(model.I, model.T, domain=NonNegativeIntegers)  # Indicador de aumento de potencia
model.HD = Var(model.I, model.T, domain=NonNegativeIntegers)  # Indicador de disminución de potencia
model.S = Var(model.I, model.T, domain=NonNegativeIntegers)  # Indicador de sobrepaso de potencia
model.Y = Var(model.I, model.T, domain=Binary)  # Indicador de cambios realizados

# Función Objetivo
def objective_rule(model):
    fixed_costs = sum((model.ce + model.cv)*model.Y[i,t] for i in model.I for t in model.T)
    variable_costs = sum((model.cde + model.cda) * model.HU[i, t] + (model.cde + model.cda)*model.HD[i, t] + model.c[i]*2*model.S[i, t] + model.c[i]*model.k[t,i] for i in model.I for t in model.T)
    #variable_costs = sum(model.c[i]*2*model.S[i, t] + model.c[i]*model.k[t,i] for i in model.I for t in model.T)
    return fixed_costs + variable_costs
model.Objective = Objective(rule=objective_rule, sense=minimize)

# Restricciones

def power_balance_rule(model, i, t):
    if t == model.T.first():
        # P al primer periodo = potencia inicial +/- cambios
        return model.P[i, t] == model.P0[i] + model.HU[i,t] - model.HD[i,t]
    else:
        # P evoluciona solo por HU/HD
        return model.P[i, t] == model.P[i, model.T.prev(t)] + model.HU[i,t] - model.HD[i,t]

model.PowerBalance = Constraint(model.I, model.T, rule=power_balance_rule)

def overrun_rule(model, i, t):
    # S >= k - P  ⇒  si k > P, S recoge la diferencia; si no, S puede ser 0
    return model.S[i,t] >= model.k[t,i] - model.P[i,t]

model.Overrun = Constraint(model.I, model.T, rule=overrun_rule)



def change_limit_rule(model, i):
    return sum(model.Y[i, t] for i in model.I for t in model.T) <= model.N
model.ChangeLimit = Constraint(model.I, rule=change_limit_rule)

def change_definition_rule_hu(model, i, t):
    return model.HU[i, t] <= model.M*model.Y[i, t]
model.ChangeDefinitionHU = Constraint(model.I, model.T, rule=change_definition_rule_hu)

def change_definition_rule_hd(model, i, t):
    return model.HD[i, t] <= model.M*model.Y[i, t]
model.ChangeDefinitionHD = Constraint(model.I, model.T, rule=change_definition_rule_hd)

def change_definition_rule_pp(model, i, t):
    if i == model.I.first():
        return Constraint.Skip
    return model.P[i, t] >= model.P[model.I.prev(i), t]
model.ChangeDefinitionP = Constraint(model.I, model.T, rule=change_definition_rule_pp)

'''
def power_minimum_rule(model, i, t):
    return model.P[i, t] >= model.P0[i]
model.PowerMinimum = Constraint(model.I, model.T, rule=power_minimum_rule)


def power_minimum_rule2(model, i, t):
    # Evitar error en el primer periodo
    if t == model.T.first():
        return Constraint.Skip
    # Para los demás periodos
    return model.P[i, t] >= model.P[i, model.T.prev(t)]
model.PowerMinimum = Constraint(model.I, model.T, rule=power_minimum_rule2)
'''


# Instanciación y resolución del modelo
dp = DataPortal()
dp.load(filename='Asignacion_consumos_maximetros.csv', param='k', index=('T','I'))
dp.load(filename='Asignacion_tramos.csv', param=('c', 'P0'), index='I')
inst=model.create_instance(dp, name="Asignacion")
opt = SolverFactory('cbc')
results = opt.solve(inst, tee=True, options={'MIPGap': 0.05})
inst.solutions.load_from(results)
#inst.display()
print(results)
#print(f"Objective Value: {value(inst.Objective)}")

results = opt.solve(inst, tee=True, options={'MIPGap': 0.05})
inst.solutions.load_from(results)
print(results)
# print(f"Objective Value: {value(inst.Objective)}")

from pyomo.environ import value

print("\n================ RESULTADOS DEL MODELO ================\n")

# 1) Valores totales
print(f"Valor de la función objetivo: {value(inst.Objective):.2f} €\n")
print("---- Resumen globales ----")
gtotal_HU = sum(value(inst.HU[i, t]) for i in inst.I for t in inst.T)
gtotal_HD = sum(value(inst.HD[i, t]) for i in inst.I for t in inst.T)
gtotal_S  = sum(value(inst.S[i, t])  for i in inst.I for t in inst.T)
gnum_cambios = sum(value(inst.Y[i, t]) for i in inst.I for t in inst.T)
    
print(f"  Total HU (aumentos)    = {gtotal_HU:.2f} kW")
print(f"  Total HD (disminuciones)= {gtotal_HD:.2f} kW")
print(f"  Total S  (sobrepasos)   = {gtotal_S:.2f} kW")
print(f"  Nº cambios (Y=1)        = {gnum_cambios:.0f}")
print("")

# 2) Resumen por tramo (i)
print("---- Resumen por tramo (i) ----")
last_T = inst.T.last()
for i in inst.I:
    P0_i = value(inst.P0[i])
    P_final = value(inst.P[i, last_T])
    P_max = max(value(inst.P[i, t]) for t in inst.T)
    total_HU = sum(value(inst.HU[i, t]) for t in inst.T)
    total_HD = sum(value(inst.HD[i, t]) for t in inst.T)
    total_S  = sum(value(inst.S[i, t])  for t in inst.T)
    num_cambios = sum(value(inst.Y[i, t]) for t in inst.T)

    print(f"Tramo i={i}:")
    print(f"  P0 = {P0_i:.2f} kW")
    print(f"  P_final (t={last_T}) = {P_final:.2f} kW")
    print(f"  P_max   = {P_max:.2f} kW")
    print(f"  Total HU (aumentos)    = {total_HU:.2f} kW")
    print(f"  Total HD (disminuciones)= {total_HD:.2f} kW")
    print(f"  Total S  (sobrepasos)   = {total_S:.2f} kW")
    print(f"  Nº cambios (Y=1)        = {num_cambios:.0f}")
    print("")


# 3) Tabla de potencias P(i,t)
print("\n---- Potencias P(i,t) por periodo ----")
# Cabecera
cabecera = ["t"] + [f"P[{i}]" for i in inst.I]
print("  ".join(f"{h:>8}" for h in cabecera))

for t in inst.T:
    fila = [f"{t:>8}"]
    for i in inst.I:
        fila.append(f"{value(inst.P[i, t]):8.2f}")
    print("  ".join(fila))


# 4) Cambios de potencia entre periodos (ΔP) y cambios activados (Y)
print("\n---- Cambios de potencia por tramo y periodo ----")
for i in inst.I:
    print(f"\nTramo i={i}:")
    for t in inst.T:
        P_t = value(inst.P[i, t])
        if t == inst.T.first():
            P_prev = value(inst.P0[i])
        else:
            t_prev = inst.T.prev(t)
            P_prev = value(inst.P[i, t_prev])

        delta_P = P_t - P_prev
        HU_it = value(inst.HU[i, t])
        HD_it = value(inst.HD[i, t])
        S_it  = value(inst.S[i, t])
        Y_it  = value(inst.Y[i, t])

        # Solo mostramos periodos donde haya algo interesante
        if abs(delta_P) > 1e-6 or HU_it > 0 or HD_it > 0 or S_it > 0 or Y_it > 0:
            print(
                f"  t={t:2d}: P_prev={P_prev:7.2f} -> P={P_t:7.2f}  "
                f"ΔP={delta_P:7.2f}  HU={HU_it:6.2f}  HD={HD_it:6.2f}  "
                f"S={S_it:6.2f}  Y={int(round(Y_it))}"
            )


# 5) Sobrepasos S(i,t) explícitos
print("\n---- Sobrepasos de potencia (S[i,t] > 0) ----")
hay_sobrepasos = False
for i in inst.I:
    for t in inst.T:
        S_it = value(inst.S[i, t])
        if S_it > 1e-6:
            if not hay_sobrepasos:
                hay_sobrepasos = True
            print(f"  i={i}, t={t}: S={S_it:.2f} kW")

if not hay_sobrepasos:
    print("  No se han producido sobrepasos de potencia (S=0 en todos los periodos).")

print("\n================ FIN DE RESULTADOS ================\n")
