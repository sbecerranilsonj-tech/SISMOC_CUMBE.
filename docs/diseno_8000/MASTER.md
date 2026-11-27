# Design System Master File

> **LOGIC:** When building a specific page, first check `design-system/pages/[page-name].md`.
> If that file exists, its rules **override** this Master file.
> If not, strictly follow the rules below.

---

**Project:** SISMOC Contabilidad
**Generated:** 2026-11-12 17:35:56
**Category:** General
**Design Dials:** Variance 6/10 (Balanced / Modern) | Motion 3/10 (Subtle) | Density 7/10 (Standard)

---

## Global Rules

### Color Palette

| Role | Hex | CSS Variable |
|------|-----|--------------|
| Primary | `#173C35` | `--color-primary` |
| On Primary | `#FFFFFF` | `--color-on-primary` |
| Secondary | `#315C53` | `--color-secondary` |
| On Secondary | `#000000` | `--color-on-secondary` |
| Accent/CTA | `#B94B16` | `--color-accent` |
| On Accent/CTA | `#FFFFFF` | `--color-on-accent` |
| Background | `#F3F6F7` | `--color-background` |
| Foreground | `#20343B` | `--color-foreground` |
| Card | `#FFFFFF` | `--color-card` |
| Card Foreground | `#20343B` | `--color-card-foreground` |
| Muted | `#EDF3F2` | `--color-muted` |
| Muted Foreground | `#52676C` | `--color-muted-foreground` |
| Border | `#DCE6E5` | `--color-border` |
| Destructive | `#DC2626` | `--color-destructive` |
| On Destructive | `#FFFFFF` | `--color-on-destructive` |
| Ring | `#B94B16` | `--color-ring` |

**Color Notes:** Adaptacion de marca revisada. Teal #087F78 para indicadores informativos, no sustituye los estados textuales.

### Typography

- **Heading Font:** Geist local
- **Body Font:** Geist local, Segoe UI
- **Mood:** Precision contable, numerales tabulares y lectura prolongada

### Spacing Variables

*Density: 7/10 — Standard*

| Token | Value | Usage |
|-------|-------|-------|
| `--space-xs` | `4px` / `0.25rem` | Tight gaps |
| `--space-sm` | `8px` / `0.5rem` | Icon gaps, inline spacing |
| `--space-md` | `16px` / `1rem` | Standard padding |
| `--space-lg` | `24px` / `1.5rem` | Section padding |
| `--space-xl` | `32px` / `2rem` | Large gaps |
| `--space-2xl` | `48px` / `3rem` | Section margins |
| `--space-3xl` | `64px` / `4rem` | Hero padding |

### Shadow Depths

| Level | Value | Usage |
|-------|-------|-------|
| `--shadow-sm` | `0 1px 2px rgba(0,0,0,0.05)` | Subtle lift |
| `--shadow-md` | `0 4px 6px rgba(0,0,0,0.1)` | Cards, buttons |
| `--shadow-lg` | `0 10px 15px rgba(0,0,0,0.1)` | Modals, dropdowns |
| `--shadow-xl` | `0 20px 25px rgba(0,0,0,0.15)` | Hero images, featured cards |

---

## Component Specs

### Buttons

```css
/* Primary Button */
.btn-primary {
  background: #B94B16;
  color: #FFFFFF;
  padding: 12px 24px;
  border-radius: 8px;
  font-weight: 600;
  transition: all 200ms ease;
  cursor: pointer;
}

.btn-primary:hover {
  opacity: 0.9;
  transform: translateY(-1px);
}

/* Secondary Button */
.btn-secondary {
  background: transparent;
  color: #173C35;
  border: 2px solid #173C35;
  padding: 12px 24px;
  border-radius: 8px;
  font-weight: 600;
  transition: all 200ms ease;
  cursor: pointer;
}
```

### Cards

```css
.card {
  background: #F3F6F7;
  border-radius: 12px;
  padding: 24px;
  box-shadow: var(--shadow-md);
  transition: all 200ms ease;
  cursor: pointer;
}

.card:hover {
  box-shadow: var(--shadow-lg);
  transform: translateY(-2px);
}
```

### Inputs

```css
.input {
  padding: 12px 16px;
  border: 1px solid #E2E8F0;
  border-radius: 8px;
  font-size: 16px;
  transition: border-color 200ms ease;
}

.input:focus {
  border-color: #173C35;
  outline: none;
  box-shadow: 0 0 0 3px #173C3520;
}
```

### Modals

```css
.modal-overlay {
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px);
}

.modal {
  background: white;
  border-radius: 16px;
  padding: 32px;
  box-shadow: var(--shadow-xl);
  max-width: 500px;
  width: 90%;
}
```

---

## Style Guidelines

**Style:** Precision suave · El Cumbe

**Keywords:** Clean, simple, spacious, functional, white space, high contrast, geometric, sans-serif, grid-based, essential

**Best For:** Enterprise apps, dashboards, documentation sites, SaaS platforms, professional tools

**Key Effects:** Subtle hover (200-250ms), smooth transitions, sharp shadows if any, clear type hierarchy, fast loading

### Page Pattern

**Pattern Name:** Centro de control contable

- **Conversion Strategy:** Reducir errores al revisar asistencia importada e itinerarios; sin llamadas comerciales ni datos ficticios.
- **CTA Placement:** Una accion principal por tarea, acciones secundarias junto a sus registros
- **Section Order:** Navegacion lateral > periodo y filtros > resumen de revision > tabla operativa > acciones existentes

---

## Motion

Implementacion revisada: CSS nativo, sin instalar GSAP. Entrada de panel con opacity y translateY(6px), 220ms ease-out. Botones y foco: 160ms. Sin animaciones infinitas, sin mover filas durante la revision. prefers-reduced-motion desactiva transiciones y animaciones.

## Anti-Patterns (Do NOT Use)

- ❌ No neon sobre tablas, sin hero comercial, sin animaciones continuas, sin indicadores inventados, sin cambios en permisos, importaciones o calculos.

### Additional Forbidden Patterns

- ❌ **Emojis as icons** — Use SVG icons (Heroicons, Lucide, Simple Icons)
- ❌ **Missing cursor:pointer** — All clickable elements must have cursor:pointer
- ❌ **Layout-shifting hovers** — Avoid scale transforms that shift layout
- ❌ **Low contrast text** — Maintain 4.5:1 minimum contrast ratio
- ❌ **Instant state changes** — Always use transitions (150-300ms)
- ❌ **Invisible focus states** — Focus states must be visible for a11y

---

## Pre-Delivery Checklist

Before delivering any UI code, verify:

- [ ] No emojis used as icons (use SVG instead)
- [ ] All icons from consistent icon set (Heroicons/Lucide)
- [ ] `cursor-pointer` on all clickable elements
- [ ] Hover states with smooth transitions (150-300ms)
- [ ] Light mode: text contrast 4.5:1 minimum
- [ ] Focus states visible for keyboard navigation
- [ ] `prefers-reduced-motion` respected
- [ ] Responsive: 375px, 768px, 1024px, 1440px
- [ ] No content hidden behind fixed navbars
- [ ] No horizontal scroll on mobile


## Especificacion aprobada para este proyecto
- Audiencia: contabilidad de empresa de transportes; uso diario de Excel de huellero e itinerarios.
- Stack: Django templates + Tailwind CSS; escritorio pywebview.
- Diales: --variance 6 --motion 3 --density 7.
- La busqueda general no produjo un patron administrativo exacto. Se revisaron las recomendaciones y se sustituyo el patron de landing por la estructura operativa existente.
- Texto de tabla y campos 14px, etiquetas y cabeceras 13px, secundarios 12px, titulos 22px. Numerales tabulares.
- Separacion 8/12/16/24/32px, radios 10/14/20px, controles 44px.
- Movimiento CSS: entrada 220ms y respuesta 160ms; sin GSAP ni dependencias de animacion. Desactivar con prefers-reduced-motion.
- Las tablas desbordan dentro de su contenedor; nunca ocultar columnas ni alterar los registros.
- No modificar backend, API, datos, calculos, nombres de campos ni controladores de eventos.
- Fuente: UI UX Pro Max, https://github.com/nextlevelbuilder/ui-ux-pro-max-skill ; licencia MIT incluida en .agents/skills/ui-ux-pro-max/LICENSE.
- Implementacion: frontend/assets/pro-max.css, compilada en frontend/static/app.css.

La consulta especifica html-tailwind no devolvio coincidencias tras un reintento. La adaptacion responsive usa los criterios generales de accesibilidad del skill y CSS/Tailwind del proyecto; no se atribuye a una coincidencia de esa base.

## Redaccion de interfaz
Eliminar subtitulos que repiten titulos o acciones evidentes. Conservar errores, alcance de fechas, estado, datos de origen y advertencias sobre aprobacion/cierre. Texto auxiliar de una frase cuando sea suficiente.

## Alineación y acciones compactas
Mantener campos y botones en una misma línea base, con alturas uniformes y espacios consistentes. Usar botones compactos para subir archivos, con el selector oculto. Abrir configuraciones secundarias desde un botón para preservar el espacio de la vista principal. En móvil, distribuir controles en columnas completas sin desbordamientos.

La alineación común se implementa en `static/alineacion.css`, cargada después de los estilos de cada módulo en la plantilla principal y en las páginas independientes de horarios. Controles de formulario: 44 px; filtros compactos de asistencia: 38 px; acciones de tabla: mínimo 32 px. Alinear las acciones con la base del campo y evitar que el texto de ayuda desplace los botones. Mantener las tablas anchas dentro de sus contenedores con desplazamiento horizontal.
