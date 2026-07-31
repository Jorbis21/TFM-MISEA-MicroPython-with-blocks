# utils/procesamiento_matrices.py

def fusionar_matrices_espaciales(matriz_base, matriz_nueva, nexos_esperados, direccion="desconocida"):
    """
    Toma dos matrices de bloques detectados por visión artificial y las fusiona 
    basándose en los nexos y la dirección de desbordamiento.
    """
    genericos = ["valor_variable", "numero", "texto", "verdadero", "falso", "imagen"]
    nexos_fuertes = [n for n in nexos_esperados if str(n).strip().lower() not in genericos]
    anclajes = nexos_fuertes if nexos_fuertes else nexos_esperados
    
    nueva_super_matriz = [fila.copy() for fila in matriz_base]
    
    if direccion == "lateral":
        filas_mapeadas_en_nueva = set()
        offset_c_global = 0 
        
        for nexo in anclajes:
            nexo_str = str(nexo).strip().lower()
            r_base, c_base, r_nueva, c_nueva = -1, -1, -1, -1
            
            for r in range(len(nueva_super_matriz)):
                for c in range(len(nueva_super_matriz[r])):
                    if str(nueva_super_matriz[r][c]).strip().lower() == nexo_str:
                        r_base, c_base = r, c
                        break
                if r_base != -1: break
            
            for r in range(len(matriz_nueva)):
                for c in range(len(matriz_nueva[r])):
                    if str(matriz_nueva[r][c]).strip().lower() == nexo_str:
                        r_nueva, c_nueva = r, c
                        break
                if r_nueva != -1: break
            
            if r_base != -1 and r_nueva != -1:
                filas_mapeadas_en_nueva.add(r_nueva)
                offset_c_global = c_base - c_nueva
                
                for c in range(c_nueva + 1, len(matriz_nueva[r_nueva])):
                    val = matriz_nueva[r_nueva][c]
                    target_c = c + offset_c_global
                    while len(nueva_super_matriz[r_base]) <= target_c:
                        nueva_super_matriz[r_base].append("")
                    if val != "":
                        nueva_super_matriz[r_base][target_c] = val
                        
        if filas_mapeadas_en_nueva:
            max_r_mapeada = max(filas_mapeadas_en_nueva)
            for r in range(max_r_mapeada + 1, len(matriz_nueva)):
                nueva_fila = []
                for c in range(len(matriz_nueva[r])):
                    val = matriz_nueva[r][c]
                    target_c = c + offset_c_global
                    if target_c >= 0:
                        while len(nueva_fila) <= target_c:
                            nueva_fila.append("")
                        if val != "":
                            nueva_fila[target_c] = val
                nueva_super_matriz.append(nueva_fila)
        else:
            for r in range(len(matriz_nueva)):
                nueva_super_matriz.append(matriz_nueva[r])
                
    elif direccion == "inferior":
        ancla_base_r, c_base = -1, -1
        ancla_nueva_r, c_nueva = -1, -1
        nexo_usado = None
        
        for nexo in anclajes:
            nexo_str = str(nexo).strip().lower()
            for r in range(len(nueva_super_matriz)-1, -1, -1):
                for c in range(len(nueva_super_matriz[r])):
                    if str(nueva_super_matriz[r][c]).strip().lower() == nexo_str:
                        ancla_base_r, c_base = r, c
                        break
                if ancla_base_r != -1: break
            
            for r in range(len(matriz_nueva)):
                for c in range(len(matriz_nueva[r])):
                    if str(matriz_nueva[r][c]).strip().lower() == nexo_str:
                        ancla_nueva_r, c_nueva = r, c
                        break
                if ancla_nueva_r != -1: break
            
            if ancla_base_r != -1 and ancla_nueva_r != -1:
                nexo_usado = nexo
                break
        
        if nexo_usado:
            offset_c = c_base - c_nueva
            
            for c in range(c_nueva + 1, len(matriz_nueva[ancla_nueva_r])):
                val = matriz_nueva[ancla_nueva_r][c]
                target_c = c + offset_c
                while len(nueva_super_matriz[ancla_base_r]) <= target_c:
                    nueva_super_matriz[ancla_base_r].append("")
                if val != "":
                    nueva_super_matriz[ancla_base_r][target_c] = val
            
            for r in range(ancla_nueva_r + 1, len(matriz_nueva)):
                nueva_fila = []
                for c in range(len(matriz_nueva[r])):
                    val = matriz_nueva[r][c]
                    target_c = c + offset_c
                    if target_c >= 0:
                        while len(nueva_fila) <= target_c:
                            nueva_fila.append("")
                        if val != "":
                            nueva_fila[target_c] = val
                nueva_super_matriz.append(nueva_fila)
        else:
            for r in range(len(matriz_nueva)):
                nueva_super_matriz.append(matriz_nueva[r])
    else:
        for r in range(len(matriz_nueva)):
            nueva_super_matriz.append(matriz_nueva[r])
            
    return nueva_super_matriz