# RNA Structure Analysis Tool

A powerful web-based application for analyzing RNA sequences and structures, built with Streamlit and ViennaRNA.

## Features

- **File Upload**: Support for FASTA format files up to 1GB
- **RNA Structure Analysis**: 
  - Secondary structure prediction
  - Energy calculations
  - Base pair probability analysis
- **Interactive Visualization**:
  - Structure plots
  - Statistical analysis
  - Pattern recognition
- **Advanced Analysis**:
  - Splice site detection
  - Motif analysis
  - GC content analysis

## Screenshots

### Main Interface
[Insert screenshot of the main interface]

### Structure Visualization
[Insert screenshot of RNA structure visualization]

### Analysis Results
[Insert screenshot of analysis results]

## Installation

1. Clone the repository:
```bash
git clone [your-repository-url]
cd [repository-name]
```

2. Create and activate conda environment:
```bash
conda create -n rnag python=3.9
conda activate rnag
```

3. Install dependencies:
```bash
conda install -c conda-forge -c bioconda viennarna scipy matplotlib streamlit numpy pandas biopython plotly
```

4. Run the application:
```bash
streamlit run app.py
```

## Usage

1. Upload your FASTA format file (up to 1GB)
2. Configure analysis parameters:
   - Window size
   - Step size
   - Sample percentage
   - Delta G threshold
   - Min/Max intron length
3. Click "Analyze Genome" to start the analysis
4. View and interact with the results

## Requirements

- Python 3.9+
- ViennaRNA
- Streamlit
- NumPy
- Pandas
- BioPython
- Matplotlib
- Plotly
- SciPy

## Contributing

Feel free to submit issues and enhancement requests!

## License

[Insert your chosen license]

## Contact

[Insert your contact information] 