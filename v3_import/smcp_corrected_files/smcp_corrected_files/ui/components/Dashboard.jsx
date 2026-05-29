import React from 'react';
import { Grid, Paper, Typography } from '@mui/material';

export default function Dashboard({ data = {} }) {
  const signal = data.signals?.[0];
  const narrative = data.narratives?.[0];
  return (
    <Grid container spacing={2} style={{ padding: 20 }} dir="rtl">
      <Grid item xs={12}><Paper style={{ padding: 20 }}><Typography variant="h4">داشبورد نهادی</Typography><Typography variant="body2">وضعیت بازار: {data.market_state || 'نامشخص'}</Typography></Paper></Grid>
      <Grid item xs={6}><Paper style={{ padding: 20, minHeight: 220 }}><Typography variant="h6">آخرین کاندید سیگنال</Typography>{signal ? (<><Typography>جهت: {signal.direction}</Typography><Typography>احتمال: {signal.probability}</Typography><Typography>اطمینان: {signal.confidence}</Typography><Typography>ریسک: {signal.risk_grade}</Typography><Typography>زمان‌بندی: {signal.execution_timing}</Typography></>) : <Typography>هنوز سیگنالی دریافت نشده است.</Typography>}</Paper></Grid>
      <Grid item xs={6}><Paper style={{ padding: 20, minHeight: 220 }}><Typography variant="h6">روایت بازار</Typography><Typography>{narrative?.persian_text || 'هنوز روایتی دریافت نشده است.'}</Typography></Paper></Grid>
      <Grid item xs={12}><Paper style={{ padding: 20, maxHeight: 300, overflow: 'auto' }}><Typography variant="h6">Debug JSON</Typography><pre>{JSON.stringify(data, null, 2)}</pre></Paper></Grid>
    </Grid>
  );
}
