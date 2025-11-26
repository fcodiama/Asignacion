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
model.E = Var(model.I, model.T, domain=NonNegativeIntegers)  # sobrepaso de potencia por encima del 5% de P
model.Y = Var(model.T, domain=Binary)  # Indicador de cambios realizados
# Variables auxiliares: cambio máximo por periodo (para costes)
model.U = Var(model.T, domain=NonNegativeIntegers)  # cambio máximo de subida en t
model.D = Var(model.T, domain=NonNegativeIntegers)  # cambio máximo de bajada en t



# Función Objetivo
def objective_rule(model):
    fixed_costs = sum((model.ce + model.cv)*model.Y[t] for t in model.T)
    variable_costs = sum((model.cde + model.cda) * (model.U[t] + model.D[t]) + model.c[i]*2*model.E[i, t] + model.c[i]*(model.S[i,t]-model.E[i,t])+ model.c[i]*model.k[t,i] for i in model.I for t in model.T)
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

def excess_over_5pct_lower_rule(model, i, t):
    # E >= S - 0.05·P  (si S > 0.05P, E recoge el exceso)
    return model.E[i,t] >= model.S[i,t] - 0.05 * model.P[i,t]
model.ExcessOver5PctLower = Constraint(model.I, model.T, rule=excess_over_5pct_lower_rule)


def excess_over_5pct_upper_rule(model, i, t):
    # E <= S  (por seguridad, para que E no crezca más que S)
    return model.E[i,t] <= model.S[i,t]
model.ExcessOver5PctUpper = Constraint(model.I, model.T, rule=excess_over_5pct_upper_rule)


def change_limit_rule(model):
    # Máximo N periodos con cambios en todo el año
    return sum(model.Y[t] for t in model.T) <= model.N
model.ChangeLimit = Constraint(rule=change_limit_rule)


def change_definition_rule_hu(model, i, t):
    # Si hay HU en (i,t), entonces Y[t] debe ser 1
    return model.HU[i, t] <= model.M * model.Y[t]
model.ChangeDefinitionHU = Constraint(model.I, model.T, rule=change_definition_rule_hu)

def change_definition_rule_hd(model, i, t):
    # Si hay HD en (i,t), entonces Y[t] debe ser 1
    return model.HD[i, t] <= model.M * model.Y[t]
model.ChangeDefinitionHD = Constraint(model.I, model.T, rule=change_definition_rule_hd)

def max_up_change_rule(model, i, t):
    # U[t] >= HU[i,t] para todo i
    return model.U[t] >= model.HU[i, t]
model.MaxUpChange = Constraint(model.I, model.T, rule=max_up_change_rule)

def max_down_change_rule(model, i, t):
    # D[t] >= HD[i,t] para todo i
    return model.D[t] >= model.HD[i, t]
model.MaxDownChange = Constraint(model.I, model.T, rule=max_down_change_rule)


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
dp.load(filename='Asignacion_consumos_optimizados.csv', param='k', index=('T','I'))
dp.load(filename='Asignacion_tramos.csv', param=('c', 'P0'), index='I')
inst=model.create_instance(dp, name="Asignacion")
opt = SolverFactory('cbc')
results = opt.solve(inst, tee=True, options={'MIPGap': 0.05})
inst.solutions.load_from(results)
#inst.display()
print(results)
#print(f"Objective Value: {value(inst.Objective)}")


from pyomo.environ import value

'''
print("\n================ RESULTADOS DEL MODELO ================\n")

# 1) Valores totales
print(f"Valor de la función objetivo: {value(inst.Objective):.2f} €\n")
print("---- Resumen globales ----")
gtotal_HU = sum(value(inst.HU[i, t]) for i in inst.I for t in inst.T)
gtotal_HD = sum(value(inst.HD[i, t]) for i in inst.I for t in inst.T)
gtotal_S  = sum(value(inst.S[i, t])  for i in inst.I for t in inst.T)
gtotal_E  = sum(value(inst.E[i, t])  for i in inst.I for t in inst.T)
gnum_cambios = sum(value(inst.Y[i, t]) for i in inst.I for t in inst.T)
    
print(f"  Total HU (aumentos)    = {gtotal_HU:.2f} kW")
print(f"  Total HD (disminuciones)= {gtotal_HD:.2f} kW")
print(f"  Total S  (sobrepasos)   = {gtotal_S:.2f} kW")
print(f"  Total E  (exceso >5%)   = {gtotal_E:.2f} kW")
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
    total_E  = sum(value(inst.E[i, t])  for t in inst.T)
    num_cambios = sum(value(inst.Y[i, t]) for t in inst.T)

    print(f"Tramo i={i}:")
    print(f"  P0 = {P0_i:.2f} kW")
    print(f"  P_final (t={last_T}) = {P_final:.2f} kW")
    print(f"  P_max   = {P_max:.2f} kW")
    print(f"  Total HU (aumentos)    = {total_HU:.2f} kW")
    print(f"  Total HD (disminuciones)= {total_HD:.2f} kW")
    print(f"  Total S  (sobrepasos)   = {total_S:.2f} kW")
    print(f"  Total E  (exceso >5%)   = {total_E:.2f} kW")
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
        E_it  = value(inst.E[i, t])

        # Solo mostramos periodos donde haya algo interesante
        if abs(delta_P) > 1e-6 or HU_it > 0 or HD_it > 0 or S_it > 0 or Y_it > 0 or E_it > 0:
            print(
                f"  t={t:2d}: P_prev={P_prev:7.2f} -> P={P_t:7.2f}  "
                f"ΔP={delta_P:7.2f}  HU={HU_it:6.2f}  HD={HD_it:6.2f}  "
                f"S={S_it:6.2f}  Y={int(round(Y_it))}  E={E_it:6.2f}"
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

# 6) Excesos E(i,t) explícitos
print("\n---- Excesos de potencia (E[i,t] > 0) ----")
hay_excesos = False
for i in inst.I:
    for t in inst.T:
        E_it = value(inst.E[i, t])
        if E_it > 1e-6:
            if not hay_excesos:
                hay_excesos = True
            print(f"  i={i}, t={t}: E={E_it:.2f} kW")

if not hay_excesos:
    print("  No se han producido excesos de potencia (E=0 en todos los periodos).")

print("\n================ FIN DE RESULTADOS ================\n")
'''

# ======= BLOQUE DE EXPORTACIÓN A TXT =======
from pyomo.environ import value

with open("Resultados_Asignacion_optimizado.txt", "w") as f:

    # ====================================================
    # 1. VALOR DE LA FUNCIÓN OBJETIVO
    # ====================================================
    f.write("=== VALOR DE LA FUNCIÓN OBJETIVO ===\n")
    f.write(f"Objetivo = {value(inst.Objective):.4f} €\n\n")

    # ====================================================
    # 2. RESUMEN GLOBAL
    # ====================================================
    f.write("=== RESUMEN GLOBAL ===\n")

    gtotal_HU = sum(value(inst.HU[i, t]) for i in inst.I for t in inst.T)
    gtotal_HD = sum(value(inst.HD[i, t]) for i in inst.I for t in inst.T)
    gtotal_S  = sum(value(inst.S[i, t])  for i in inst.I for t in inst.T)

    if hasattr(inst, "E"):
        gtotal_E  = sum(value(inst.E[i, t])  for i in inst.I for t in inst.T)
    else:
        gtotal_E = None

    if hasattr(inst, "U") and hasattr(inst, "D"):
        gtotal_U = sum(value(inst.U[t]) for t in inst.T)
        gtotal_D = sum(value(inst.D[t]) for t in inst.T)
    else:
        gtotal_U = gtotal_D = None

    gnum_cambios = sum(1 for t in inst.T if value(inst.Y[t]) > 0.5)

    f.write(f"  Total HU (aumentos)         = {gtotal_HU:.2f} kW\n")
    f.write(f"  Total HD (disminuciones)     = {gtotal_HD:.2f} kW\n")
    f.write(f"  Total S  (sobrepasos)        = {gtotal_S:.2f} kW\n")

    if gtotal_E is not None:
        f.write(f"  Total E  (exceso >5%)        = {gtotal_E:.2f} kW\n")

    if gtotal_U is not None and gtotal_D is not None:
        f.write(f"  Total U (max subidas por t)  = {gtotal_U:.2f} kW\n")
        f.write(f"  Total D (max bajadas por t)  = {gtotal_D:.2f} kW\n")

    f.write(f"  Nº periodos con cambios Y    = {gnum_cambios:.0f}\n\n")

    # ====================================================
    # 2A. RESUMEN FINAL DE Y(t)
    # ====================================================
    f.write("\n\n=== PERIODOS CON ACTIVACIÓN DE CAMBIOS Y(t) ===\n")
    hubo_Y = False
    for t in inst.T:
        y_val = value(inst.Y[t])
        if y_val > 0.5:
            if not hubo_Y:
                hubo_Y = True
            f.write(f"  t={t}: Y[t] = 1\n")
    if not hubo_Y:
        f.write("  No hubo periodos con activaciones de cambio (Y[t]=0 para todo t).\n")


    # ====================================================
    # 2B. CAMBIOS Y COSTES ASOCIADOS POR PERIODO
    # ====================================================
    f.write("\n=== CAMBIOS Y COSTES ASOCIADOS POR PERIODO ===\n")

    tol = 1e-6
    hubo_algo = False

    for t in inst.T:
        # ¿Hay algún cambio HU/HD en este periodo?
        hay_cambios_t = any(
            abs(value(inst.HU[i, t])) > tol or abs(value(inst.HD[i, t])) > tol
            for i in inst.I
        )
        if not hay_cambios_t and value(inst.Y[t]) <= 0.5:
            continue  # nada interesante en este periodo

        hubo_algo = True
        Yt = value(inst.Y[t])

        f.write(f"\nPeriodo t = {t}:\n")
        f.write(f"  Y[t] = {int(round(Yt))}  -> ")
        if Yt > 0.5:
            f.write("Se paga coste fijo (ce+cv).\n")
        else:
            f.write("No se paga coste fijo (ce+cv).\n")

        # Valores de U y D si existen
        if hasattr(inst, "U") and hasattr(inst, "D"):
            Ut = value(inst.U[t])
            Dt = value(inst.D[t])
            f.write(f"  U[t] (máx subida considerada en coste) = {Ut:.2f} kW\n")
            f.write(f"  D[t] (máx bajada considerada en coste) = {Dt:.2f} kW\n")
        else:
            Ut = Dt = 0.0
            f.write("  [Aviso] No están definidas U[t] y D[t] en el modelo.\n")

        # Detalle por tramo
        for i in inst.I:
            hu = value(inst.HU[i, t])
            hd = value(inst.HD[i, t])

            if abs(hu) <= tol and abs(hd) <= tol:
                continue  # este tramo no cambia en t

            # ¿Este cambio de subida es el que genera coste (U[t])?
            paga_subida = (abs(hu) > tol and abs(hu - Ut) <= tol)
            # ¿Este cambio de bajada es el que genera coste (D[t])?
            paga_bajada = (abs(hd) > tol and abs(hd - Dt) <= tol)

            f.write(f"  Tramo i={i}: HU={hu:.2f} kW, HD={hd:.2f} kW")

            detalles = []
            if paga_subida:
                detalles.append("subida contabilizada en U[t]")
            if paga_bajada:
                detalles.append("bajada contabilizada en D[t]")

            if detalles:
                f.write("  -> COSTE potencia por " + " y ".join(detalles))
            else:
                f.write("  -> cambio SIN coste variable extra de potencia (solo influye en P)")

            f.write("\n")

    if not hubo_algo:
        f.write("\nNo se registraron cambios de potencia ni costes asociados.\n")

    '''
    # ====================================================
    # 3. RESUMEN POR PERIODO (SOLO T CON CAMBIOS)
    # ====================================================
    f.write("\n=== RESUMEN POR PERIODO (t con cambios) ===\n")

    hubo_periodos_cambio = False
    for t in inst.T:
        if value(inst.Y[t]) > 0.5:
            hubo_periodos_cambio = True
            f.write(f"\nPeriodo t = {t} (Y[t] = 1)\n")

            if hasattr(inst, "U") and hasattr(inst, "D"):
                f.write(f"  U[t] (máx subida) = {value(inst.U[t]):.2f} kW\n")
                f.write(f"  D[t] (máx bajada) = {value(inst.D[t]):.2f} kW\n")

            # Tramos que cambian en este periodo
            for i in inst.I:
                hu = value(inst.HU[i, t])
                hd = value(inst.HD[i, t])
                if abs(hu) > 1e-6 or abs(hd) > 1e-6:
                    f.write(f"    Tramo i={i}: HU={hu:.2f} kW, HD={hd:.2f} kW\n")

    if not hubo_periodos_cambio:
        f.write("  No hubo periodos con cambios de potencia (Y[t] = 0 para todo t).\n")

    f.write("\n")

    '''
    # ====================================================
    # 4. RESUMEN POR TRAMO
    # ====================================================
    f.write("\n=== RESUMEN POR TRAMO ===\n\n")

    for i in inst.I:
        P0_i = value(inst.P0[i])
        P_final = value(inst.P[i, inst.T.last()])
        P_max = max(value(inst.P[i, t]) for t in inst.T)
        total_HU_i = sum(value(inst.HU[i, t]) for t in inst.T)
        total_HD_i = sum(value(inst.HD[i, t]) for t in inst.T)
        total_S_i  = sum(value(inst.S[i, t])  for t in inst.T)

        if hasattr(inst, "E"):
            total_E_i = sum(value(inst.E[i, t]) for t in inst.T)
        else:
            total_E_i = None

        num_periodos_cambio_i = sum(
            1 for t in inst.T
            if abs(value(inst.HU[i, t])) > 1e-6 or abs(value(inst.HD[i, t])) > 1e-6
        )

        f.write(f"Tramo i={i}:\n")
        f.write(f"  P0 inicial                 = {P0_i:.2f} kW\n")
        f.write(f"  P final (t={inst.T.last()}) = {P_final:.2f} kW\n")
        f.write(f"  P máxima                   = {P_max:.2f} kW\n")
        f.write(f"  Total HU (aumentos)        = {total_HU_i:.2f} kW\n")
        f.write(f"  Total HD (bajadas)         = {total_HD_i:.2f} kW\n")
        f.write(f"  Total S (sobrepasos)       = {total_S_i:.2f} kW\n")

        if total_E_i is not None:
            f.write(f"  Total E (>5% exceso)       = {total_E_i:.2f} kW\n")

        f.write(f"  Nº periodos con cambios i  = {num_periodos_cambio_i}\n\n")

    # ====================================================
    # 5. DETALLE DE SOBREPASOS S(i,t)
    # ====================================================
    f.write("=== SOBREPASOS S(i,t) (solo S>0) ===\n")
    hubo_sobrepaso = False
    for i in inst.I:
        for t in inst.T:
            s_val = value(inst.S[i,t])
            if s_val > 1e-6:
                if not hubo_sobrepaso:
                    hubo_sobrepaso = True
                f.write(f"  i={i}, t={t}: S={s_val:.2f} kW\n")
    if not hubo_sobrepaso:
        f.write("  No hubo sobrepasos de potencia (S=0 en todos los periodos).\n")

    f.write("\n")

    # ====================================================
    # 6. DETALLE DE EXCESOS E(i,t) (SI EXISTE)
    # ====================================================
    if hasattr(inst, "E"):
        f.write("=== EXCESOS E(i,t) (solo E>0) ===\n")
        hubo_exceso = False
        for i in inst.I:
            for t in inst.T:
                e_val = value(inst.E[i,t])
                if e_val > 1e-6:
                    if not hubo_exceso:
                        hubo_exceso = True
                    f.write(f"  i={i}, t={t}: E={e_val:.2f} kW\n")
        if not hubo_exceso:
            f.write("  No hubo excesos (E=0 en todos los periodos).\n")

        f.write("\n")

    # ====================================================
    # 7. POTENCIAS P(i,t)
    # ====================================================
    f.write("=== POTENCIAS P(i,t) ===\n")
    for i in inst.I:
        f.write(f"\nTramo i = {i}\n")
        for t in inst.T:
            f.write(f"  P[{i},{t}] = {value(inst.P[i,t]):.2f} kW\n")

    # ====================================================
    # 8. RESUMEN FINAL DE Y(t)
    # ====================================================
    f.write("\n\n=== PERIODOS CON ACTIVACIÓN DE CAMBIOS Y(t) ===\n")
    hubo_Y = False
    for t in inst.T:
        y_val = value(inst.Y[t])
        if y_val > 0.5:
            if not hubo_Y:
                hubo_Y = True
            f.write(f"  t={t}: Y[t] = 1\n")
    if not hubo_Y:
        f.write("  No hubo periodos con activaciones de cambio (Y[t]=0 para todo t).\n")

        
    f.write("\n=== FIN DE RESULTADOS ===\n")

print("Archivo generado: Resultados_Asignacion_optimizado.txt")
# =====================================================================