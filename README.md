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
![Screenshot 2025-04-15 at 17 38 13](https://github.com/user-attachments/assets/996429df-b972-4680-9a95-d75c23c40f84)


### Analysis Results
![image](https://github.com/user-attachments/assets/ba5dfad7-faf9-48a4-a6c7-6ab4538b5c59)

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

## Donation

![Screenshot 2025-04-15 at 18 14 07](https://github.com/user-attachments/assets/aeb72767-8065-49c6-819c-9abac4baf444)

## Contact

amir@logbit.info
