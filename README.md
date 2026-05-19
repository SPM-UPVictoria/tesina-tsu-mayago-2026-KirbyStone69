[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/casVlkiB)
# Plantilla de Tesis/Tesina - Universidad Politécnica de Victoria (UPV)

Este repositorio contiene la plantilla oficial para la elaboración del reporte de estadías TSU de ingeniería en tecnologías de la información e innovación digital, diseñada para los estudiantes de la Universidad Politécnica de Victoria (UPV). La plantilla está basada en \LaTeX, una herramienta profesional para la creación de documentos científicos y técnicos, lo que garantiza un formato consistente y de alta calidad para su trabajo de investigación.

## Créditos

Esta plantilla ha sido desarrollada y puesta a disposición de la comunidad estudiantil de la UPV gracias al esfuerzo de:

* **Dr. Said Polanco Martagón**
* **Dr. Marco Aurelio Nuño Magana**

## Primeros Pasos: Obtener la Plantilla

Para comenzar a trabajar en tu tesis, puedes obtener una copia de esta plantilla de dos maneras:

### Opción 1: Clonar el Repositorio (Recomendado para uso directo)

Esta opción es la más sencilla si solo necesitas una copia local del proyecto para empezar a editarla.

1.  Abre tu terminal (o Git Bash en Windows).
2.  Navega a la carpeta donde deseas guardar tu proyecto.
3.  Ejecuta el siguiente comando para clonar el repositorio:

    ```bash
    git clone [https://github.com/tu-usuario/nombre-del-repositorio.git](https://github.com/tu-usuario/nombre-del-repositorio.git)
    cd nombre-del-repositorio
    ```

### Opción 2: Forking (Recomendado para desarrolladores y contribuciones)

Si deseas mantener tu propia versión de la plantilla en tu cuenta de GitHub o si planeas hacer mejoras y contribuir al proyecto original, la mejor práctica es hacer un "fork".

1.  En la página de este repositorio en GitHub, haz clic en el botón **"Fork"** en la esquina superior derecha.
2.  Esto creará una copia del repositorio en tu propia cuenta de GitHub.
3.  Ahora, puedes clonar tu copia localmente desde tu terminal:

    ```bash
    git clone [https://github.com/tu-usuario/nombre-de-tu-fork.git](https://github.com/tu-usuario/nombre-de-tu-fork.git)
    cd nombre-de-tu-fork
    ```

## Comandos Básicos de Compilación en LaTeX

Para generar el archivo PDF de tu tesis a partir de los archivos `.tex`, necesitarás compilar el documento. Se recomienda el uso de un editor de LaTeX como Overleaf, TeXstudio, o VS Code con la extensión LaTeX Workshop, ya que automatizan este proceso.

Si prefieres hacerlo manualmente desde la terminal, aquí están los comandos básicos en el orden correcto:

1.  **Compilar el documento principal (`main.tex`)**: Este comando genera el documento y los archivos auxiliares, pero aún sin bibliografía.

    ```bash
    pdflatex main.tex
    ```

2.  **Procesar la bibliografía (`biblio.bib`)**: Este paso crea la lista de referencias.

    ```bash
    bibtex main
    ```

3.  **Volver a compilar el documento**: Se necesita una o dos compilaciones adicionales para que la bibliografía, la tabla de contenidos y las referencias cruzadas se actualicen correctamente en el PDF final.

    ```bash
    pdflatex main.tex
    pdflatex main.tex
    ```

Si utilizas un sistema de compilación más avanzado como `latexmk`, todo el proceso se puede automatizar con un solo comando:

```bash
latexmk -pdf main.tex

  > Se adjunta el archivo Z.sh con los comando adecuados para una compilación automática.