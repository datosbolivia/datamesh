-- Consulta analítica del balance de despacho eléctrico horaria por tipo de fuente
SELECT 
    tipo_generacion,
    COUNT(nodo) as total_nodos,
    ROUND(SUM(potencia_mw), 2) as potencia_total_mw,
    ROUND(AVG(frecuencia_hz), 3) as frecuencia_promedio_hz
FROM cndc_despacho_electrico
GROUP BY tipo_generacion
ORDER BY potencia_total_mw DESC;
