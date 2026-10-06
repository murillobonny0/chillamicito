import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createMonthlyReportPdf, monthlyReportFilename } from '../src/monthlyReportPdf.js';

export const sample = {
  nombre: 'Septiembre', anio: 2026, ventas: 48750, utilidadNeta: 18325.50,
  platos: 650, consumoKg: 1280.75, costoConsumido: 29624.50,
  costoMerma: 800, costoCompras: 32100, mermaKg: 34.25, utilidad: 19125.50,
};
export const options = {
  formatMoney: (value) => `Bs ${Number(value || 0).toLocaleString('es-BO', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,
  formatCantidad: (value) => Number(value || 0).toLocaleString('es-BO', { maximumFractionDigits: 3 }),
  generatedAt: new Date('2026-09-24T18:00:00Z'),
};

test('el reporte mensual cabe en A4 y no modifica los datos', () => {
  const original = structuredClone(sample);
  const doc = createMonthlyReportPdf(sample, options);
  assert.equal(doc.getNumberOfPages(), 1);
  assert.equal(Math.round(doc.internal.pageSize.getWidth()), 210);
  assert.deepEqual(sample, original);
  assert.match(doc.output(), /^%PDF-/);
});

test('admite cero, perdida e importes grandes', () => {
  for (const amount of [0, -1234.56, 9876543210.99]) {
    const doc = createMonthlyReportPdf({ ...sample, ventas: amount, utilidadNeta: amount }, options);
    assert.equal(doc.getNumberOfPages(), 1);
  }
});

test('nombre de descarga diferencia los anios', () => {
  assert.equal(monthlyReportFilename(sample), 'reporte-septiembre-2026-chillamicito.pdf');
  assert.notEqual(monthlyReportFilename(sample), monthlyReportFilename({ ...sample, anio: 2025 }));
});
