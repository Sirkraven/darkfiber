# Borrador — LinkedIn (español)

No publicado. Borrador para revisión de Alejandro. Ángulo acordado: el
bug real del M5.8/M4.1 contado como historia de método, no como logro.
Sin apertura tipo "me complace compartir". Link al final, no en el medio.

---

Hace unos meses mi sistema de detección de sismos vía fibra óptica
"confirmó" un sismo real. Un M4.1 en California, 2.8 segundos antes del
origen publicado por el USGS. Parecía el resultado que uno quiere
mostrar.

Era un bug. Dos bugs, en realidad.

El bloque que el sistema marcó como el sismo en realidad fusionaba la
llegada real con doce segundos de actividad previa sin relación —
"2.8 segundos antes del origen" era matemáticamente imposible una vez
separado bien; el núcleo real del evento llega 9.3 segundos DESPUÉS del
origen, justo lo que tarda la onda P/S real en recorrer esa distancia.
Y la "velocidad" que el sistema midió no era una medición: era
exactamente el borde de la grilla de búsqueda de velocidades, el
equivalente a que un termómetro marque siempre 40° porque ahí termina la
escala.

Lo encontramos nosotros. Nadie de afuera lo señaló. Y en vez de dejarlo
pasar, construimos dos guardas independientes que ahora bloquean este
tipo de error específicamente: una que detecta cuando una "medición" en
realidad está pegada al borde de lo que el sistema puede medir, y otra
que exige que dos métodos de medición distintos e independientes
concuerden entre sí antes de confirmar algo.

El resultado de aplicar esas guardas contra los 16 sismos reales
validados hasta ahora (4 instalaciones, USA): **cero confirmaciones
limpias.** Ocho casos donde el sistema vio señal real pero débil y no
la sobre-confirmó. Dos casos de sismos grandes y reales que el arreglo,
por su tamaño, no puede resolver bien — y el sistema lo dice, en vez de
forzar una respuesta. Cero falsas alarmas en 27 archivos sin ningún
evento catalogado.

Cero sismos confirmados no es un mal resultado acá. Es la evidencia de
que el sistema mide en serio: prefiere abstenerse antes que mentir, y
cuando se equivocó, se auto-corrigió y lo escribió en el changelog sin
vueltas.

Código abierto, con el registro completo de esta retractación incluido:
https://github.com/Sirkraven/darkfiber
