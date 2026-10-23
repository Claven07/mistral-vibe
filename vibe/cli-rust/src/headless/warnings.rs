//! Render sourced configuration diagnostics without changing the response stream.

use std::io::{self, Write};

use crate::cli::OutputFormat;
use crate::run_export::RunWarning;

pub(super) fn write(
    format: &OutputFormat,
    warnings: &[RunWarning],
    writer: &mut impl Write,
) -> io::Result<()> {
    if *format == OutputFormat::Silent {
        return Ok(());
    }
    for warning in warnings {
        if let Some(source) = warning
            .source
            .as_deref()
            .filter(|source| !source.is_empty())
        {
            writeln!(writer, "Warning: {source}: {}", warning.message)?;
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests;
