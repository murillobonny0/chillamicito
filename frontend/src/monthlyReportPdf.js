import { jsPDF } from 'jspdf';

const colors = {
  red: '#A92328', gold: '#C39745', ink: '#242424', muted: '#656565',
  line: '#E5E5E5', pale: '#F5F5F5', white: '#FFFFFF', green: '#247052',
};

export function createMonthlyReportPdf(report, { formatMoney, formatCantidad, generatedAt = new Date(), example = false }) {
  const doc = new jsPDF({ unit: 'mm', format: 'a4', compress: true });
  const margin = 18;
  const width = 174;
  const bottom = 272;
  const period = `${report.nombre} ${report.anio || ''}`.trim();
  const gainLabel = report.utilidadNeta >= 0 ? 'Ganancia final estimada' : 'Pérdida final estimada';
  const generated = generatedAt.toLocaleString('es-BO', { dateStyle: 'short', timeStyle: 'short' });
  doc.setProperties({ title: `Chillamicito | Reporte mensual | ${period}`, author: 'Chillamicito', subject: 'Ventas, costos e inventario' });

  const text = (value, x, y, size = 10, color = colors.ink, bold = false, options = {}) => {
    doc.setFont('helvetica', bold ? 'bold' : 'normal');
    doc.setFontSize(size);
    doc.setTextColor(color);
    doc.text(String(value), x, y, options);
  };
  const wrap = (value, maxWidth, size = 10, bold = false) => {
    doc.setFont('helvetica', bold ? 'bold' : 'normal');
    doc.setFontSize(size);
    return doc.splitTextToSize(String(value), maxWidth);
  };
  const fit = (value, maxWidth, size = 20) => {
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(size);
    return Math.min(size, size * maxWidth / Math.max(doc.getTextWidth(String(value)), 1));
  };
  const header = (continued = false) => {
    doc.setFillColor(colors.red);
    doc.rect(0, 0, 210, 3, 'F');
    doc.setFillColor(colors.red);
    doc.setDrawColor(colors.gold);
    doc.setLineWidth(0.7);
    doc.circle(28, 22, 10, 'FD');
    text('CH', 28, 24.4, 16, colors.white, true, { align: 'center' });
    text('CHILLAMICITO', 44, 21, 18, colors.red, true);
    text('RESTAURANTE · GESTIÓN DE STOCK', 44, 27, 8, colors.muted);
    text(continued ? 'REPORTE MENSUAL · CONTINUACIÓN' : 'REPORTE MENSUAL', margin, 46, 9, colors.red, true);
    const title = wrap(period, width, 24, true);
    text(title, margin, 57, 24, colors.ink, true);
    const end = 57 + (title.length - 1) * 9.75;
    text(example ? 'DATOS DE EJEMPLO · SIN VALIDEZ OPERATIVA' : 'Ventas, costos e inventario', margin, end + 8, 9, colors.muted);
    doc.setDrawColor(colors.gold);
    doc.setLineWidth(0.6);
    doc.line(margin, end + 13, margin + width, end + 13);
    return end + 21;
  };

  let y = header();
  const metrics = [
    ['Ventas', formatMoney(report.ventas)],
    [gainLabel, formatMoney(report.utilidadNeta)],
    ['Platos vendidos', formatCantidad(report.platos)],
    ['Consumo de insumos', `${formatCantidad(report.consumoKg)} kg`],
    ['Costo de insumos usados', formatMoney(report.costoConsumido)],
    ['Pérdida por merma', formatMoney(report.costoMerma)],
  ];
  metrics.forEach(([label, value], index) => {
    const col = index % 2;
    const row = Math.floor(index / 2);
    const x = margin + col * 90;
    const top = y + row * 30;
    doc.setFillColor(index === 1 ? colors.red : colors.pale);
    doc.rect(x, top, 84, 25, 'F');
    text(label, x + 5, top + 7, 8, index === 1 ? colors.white : colors.muted);
    text(value, x + 5, top + 18, fit(value, 74, 18), index === 1 ? colors.white : colors.ink, true);
  });
  y += 99;

  const tableHeader = () => {
    text('Detalle del mes', margin, y, 12, colors.ink, true);
    y += 5;
    doc.setFillColor(colors.red);
    doc.rect(margin, y, width, 9, 'F');
    text('CONCEPTO', margin + 4, y + 6, 8, colors.white, true);
    text('VALOR', margin + width - 4, y + 6, 8, colors.white, true, { align: 'right' });
    y += 9;
  };
  tableHeader();
  const rows = [
    ['Mes', period],
    ['Ventas', formatMoney(report.ventas)],
    ['Costo usado', formatMoney(report.costoConsumido)],
    ['Compras', formatMoney(report.costoCompras)],
    ['Merma registrada', `${formatCantidad(report.mermaKg)} kg`],
    ['Pérdida por merma', formatMoney(report.costoMerma)],
    ['Ganancia antes de merma', formatMoney(report.utilidad)],
    ['Ganancia final descontando merma', formatMoney(report.utilidadNeta)],
  ];
  rows.forEach(([label, value], index) => {
    const last = index === rows.length - 1;
    const labelLines = wrap(label, 94, 9, last);
    const valueLines = wrap(value, 64, 9, last);
    const height = Math.max(labelLines.length, valueLines.length) * 4 + 5;
    if (y + height > bottom) {
      doc.addPage();
      y = header(true);
      tableHeader();
    }
    doc.setFillColor(last ? '#F8ECEC' : index % 2 ? colors.white : colors.pale);
    doc.rect(margin, y, width, height, 'F');
    const color = last ? (report.utilidadNeta < 0 ? colors.red : colors.green) : colors.ink;
    text(labelLines, margin + 4, y + 5.8, 9, color, last);
    text(valueLines, margin + width - 4, y + 5.8, 9, color, last, { align: 'right' });
    y += height;
  });

  const pages = doc.getNumberOfPages();
  for (let page = 1; page <= pages; page++) {
    doc.setPage(page);
    doc.setDrawColor(colors.line);
    doc.setLineWidth(0.3);
    doc.line(margin, 279, margin + width, 279);
    text(`Generado: ${generated}`, margin, 285, 7, colors.muted);
    text(`${page} / ${pages}`, margin + width, 285, 8, colors.muted, false, { align: 'right' });
    text('Chillamicito · Reporte de gestión · Importes en bolivianos (Bs)', margin, 290, 7, colors.muted);
  }
  return doc;
}

export function monthlyReportFilename(report) {
  const month = String(report.nombre).normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-');
  return `reporte-${month}-${report.anio || 'mensual'}-chillamicito.pdf`;
}
