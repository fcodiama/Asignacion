from pyomo.environ import *
import numpy as np

# Modelo
model = AbstractModel()

# Índices y Conjuntos
model.I = RangeSet(1, 6)
model.T = RangeSet(1, 12)

# Parámetros
model.c = Param(model.I, default=0, domain=NonNegativeReals)  # Costos
model.k = Param(model.I, model.T, default=0, domain=NonNegativeReals)  # Consumos
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
    variable_costs = sum((model.cde + model.cda) * model.HU[i, t] + (model.cde + model.cda)*model.HD[i, t] + model.c[i]*2 * model.S[i, t] + model.c[i]*model.k[i,t] for i in model.I for t in model.T)
    return fixed_costs + variable_costs
model.Objective = Objective(rule=objective_rule, sense=minimize)

# Restricciones
def power_balance_rule(model, i, t):
    if t == model.T.first():
        return model.P[i, t] == model.P0[i] + model.HU[i,t] - model.HD[i,t] + model.S[i,t] - model.k[i, t]
    else:
        return model.P[i, t] == model.P[i, model.T.prev(t)] + model.HU[i,t] - model.HD[i,t] + model.S[i,t] - model.k[i, t]
model.PowerBalance = Constraint(model.I, model.T, rule=power_balance_rule)

def change_limit_rule(model, i):
    return sum(model.Y[i, t] for t in model.T) <= model.N
model.ChangeLimit = Constraint(model.I, rule=change_limit_rule)

def change_definition_rule_hu(model, i, t):
    return model.HU[i, t] <= model.M*model.Y[i, t]
model.ChangeDefinitionHU = Constraint(model.I, model.T, rule=change_definition_rule_hu)

def change_definition_rule_hd(model, i, t):
    return HD[i, t] <= model.M*model.Y[i, t]
model.ChangeDefinitionHD = Constraint(model.I, model.T, rule=change_definition_rule_hd)

def change_definition_rule_pp(model, i, t):
    return model.P[i, t] >= model.P[model.I.prev(i), t]
model.ChangeDefinitionP = Constraint(model.I, model.T, rule=change_definition_rule_pp)

# Instanciación y resolución del modelo
dp = DataPortal()
dp.load(filename='Asignacion_consumos.csv', param=model.k, index=(model.I, model.T))
dp.load(filename='Asignacion_tramos.csv', param=(model.c, model.P0), index=model.I)
inst=model.create_instance(dp, name=Asignacion)
opt = SolverFactory('gurobi')
results = opt.solve(inst, tee=True, options={'MIPGap': 0.05})
inst.solutions.load_from(results)
#inst.display()
print(results)
#print(f"Objective Value: {value(inst.Objective)}")