import streamlit as st
import numpy as np
import pandas as pd
from Bio import SeqIO
import gzip
from concurrent.futures import ProcessPoolExecutor
import io
from typing import Optional
import os
import RNA
import logging
import multiprocessing
from functools import lru_cache
import time
import plotly.express as px
import plotly.graph_objects as go
import json
from scipy import stats
import matplotlib.pyplot as plt
import base64
from io import BytesIO
from datetime import datetime

# Configure logging for Streamlit Cloud
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set page config for better performance
st.set_page_config(
    page_title="RNA Structure Analysis Tool",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# At the top of your file, after imports:
if 'results_df' not in st.session_state:
    st.session_state.results_df = None
if 'analysis_stopped' not in st.session_state:
    st.session_state.analysis_stopped = False
if 'progress' not in st.session_state:
    st.session_state.progress = 0
if 'status' not in st.session_state:
    st.session_state.status = ""
if 'current_findings' not in st.session_state:
    st.session_state.current_findings = None

# Performance settings optimized for Streamlit Cloud
if 'PERFORMANCE_CONFIG' not in st.session_state:
    st.session_state.PERFORMANCE_CONFIG = {
        'batch_size': 500,  # Reduced batch size for better memory management
        'update_frequency': 1000,  # More frequent updates
        'max_workers': min(multiprocessing.cpu_count(), 4),  # Limit workers for cloud
        'chunk_size': 500000  # Reduced chunk size
    }

# Add caching for expensive calculations
@st.cache_data(ttl=3600, show_spinner=True)
def calculate_inverse_fold(sequence: str, target_structure: str) -> tuple:
    """
    Calculate inverse folding for a given sequence and target structure.
    Cached for 1 hour to improve performance.
    """
    try:
        result = RNA.inverse_fold(sequence, target_structure)
        return result
    except Exception as e:
        logger.error(f"Error in inverse fold calculation: {str(e)}")
        return None, None

# RNA Structure Visualization Functions
@st.cache_data(ttl=3600, show_spinner=True)
def plot_rna_structure(sequence: str, structure: str) -> BytesIO:
    """
    Generate RNA structure plot.
    Cached for 1 hour to improve performance.
    """
    try:
        # Create figure
        fig, ax = plt.subplots(figsize=(10, 10))
        
        # Get base pair information
        pairs = RNA.ptable(structure)
        
        # Plot sequence along a line
        seq_length = len(sequence)
        x = list(range(seq_length))
        y = [0] * seq_length
        
        # Plot sequence
        ax.plot(x, y, 'k-', alpha=0.2)  # backbone line
        
        # Plot base pairs
        for i, j in enumerate(pairs[1:], 1):
            if j > i:
                # Draw arc for base pair
                center = (i + j - 2) / 2
                width = (j - i)
                height = width / 2
                ax.add_patch(plt.matplotlib.patches.Arc(
                    (center, 0), width, height, 
                    theta1=0, theta2=180, 
                    color='blue', alpha=0.3
                ))
        
        # Add sequence labels
        for i, base in enumerate(sequence):
            ax.text(i, -0.1, base, ha='center', va='top')
        
        # Customize plot
        ax.set_title("RNA Secondary Structure")
        ax.set_xlim(-1, seq_length)
        ax.set_ylim(-1, seq_length/3)
        ax.axis('off')
        
        # Convert plot to image
        buf = BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', dpi=300)
        plt.close()
        buf.seek(0)
        return buf
    except Exception as e:
        logger.error(f"Error in structure plotting: {str(e)}")
        return None

def display_structure(sequence, structure, delta_g):
    """Display RNA structure with multiple visualization options"""
    st.write("### RNA Secondary Structure Visualization")
    
    # Create tabs for different visualizations
    plot_tab, dot_bracket_tab, stats_tab = st.tabs([
        "Structure Plot", "Dot-Bracket Notation", "Structure Statistics"
    ])
    
    with plot_tab:
        # Structure visualization
        structure_img = plot_rna_structure(sequence, structure)
        if structure_img:
            st.image(structure_img)
        
        # Display energy information
        st.write(f"Minimum Free Energy: {delta_g:.2f} kcal/mol")
        
        # Display base pair information
        pairs = RNA.ptable(structure)
        st.write("### Base Pair Information")
        pair_info = []
        for i, j in enumerate(pairs[1:], 1):
            if j > i:
                pair_info.append(f"Base {i} ({sequence[i-1]}) pairs with {j} ({sequence[j-1]})")
        if pair_info:
            with st.expander("Show Base Pairs"):
                st.write("\n".join(pair_info))
    
    with dot_bracket_tab:
        # Display dot-bracket notation
        col1, col2 = st.columns(2)
        with col1:
            st.write("### Sequence")
            st.text_area("RNA Sequence", sequence, height=100)
        with col2:
            st.write("### Structure")
            st.text_area("Dot-Bracket Notation", structure, height=100)
    
    with stats_tab:
        # Structure statistics
        st.write("### Structure Statistics")
        stats = {
            'Sequence Length': len(sequence),
            'Paired Bases': structure.count('('),
            'Unpaired Bases': structure.count('.'),
            'GC Content (%)': (sequence.count('G') + sequence.count('C')) / len(sequence) * 100,
            'AU Content (%)': (sequence.count('A') + sequence.count('U')) / len(sequence) * 100,
            'Base Pairs': len([i for i, j in enumerate(pairs[1:], 1) if j > i]),
            'Minimum Free Energy': delta_g
        }
        st.write(pd.Series(stats))
        
        # Structure composition
        st.write("### Structure Composition")
        try:
            composition = {
                'G': sequence.count('G'),
                'C': sequence.count('C'),
                'A': sequence.count('A'),
                'U': sequence.count('U')
            }
            if any(composition.values()):
                st.bar_chart(composition)
                
                # Add percentage breakdown
                total_bases = sum(composition.values())
                composition_pct = {
                    base: (count/total_bases * 100) 
                    for base, count in composition.items()
                }
                st.write("Base Composition Percentages:")
                st.write(pd.Series(composition_pct).round(2).astype(str) + '%')
            else:
                st.warning("No composition data available")
        except Exception as e:
            st.warning(f"Could not display composition chart: {str(e)}")

class GenomeAnalyzer:
    def __init__(self):
        self.sequence = None
        self.results = []
        
    def load_genome(self, file_content):
        try:
            with gzip.open(io.BytesIO(file_content), 'rt') as handle:
                for record in SeqIO.parse(handle, 'fasta'):
                    self.sequence = str(record.seq)
                    break  # Get first sequence
            return True
        except Exception as e:
            raise Exception(f"Error loading genome: {str(e)}")

    def sliding_window(self, window_size: int, step_size: int, sample_percentage: float):
        """Optimized sliding window implementation"""
        if not self.sequence:
            raise Exception("No genome loaded")
        
        sequence_length = len(self.sequence)
        
        # Calculate total windows based on min and max intron lengths
        total_windows = (sequence_length - window_size + 1) // step_size
        
        # Calculate sample size
        sample_size = int(total_windows * (sample_percentage / 100))
        
        # Generate indices
        if sample_percentage < 100:
            indices = np.random.choice(
                range(0, sequence_length - window_size + 1, step_size),
                size=sample_size,
                replace=False
            )
        else:
            indices = range(0, sequence_length - window_size + 1, step_size)
        
        sequence_array = np.array(list(self.sequence))
        for idx in indices:
            # Generate windows of different lengths
            for length in range(window_size, min(window_size + 100, sequence_length - idx)):
                yield ''.join(sequence_array[idx:idx + length])

    def analyze_sequence(self, seq: str, delta_g_threshold: float):
        """Analyze a single sequence"""
        if len(seq) < 50:
            return None
        if not ((seq.startswith('GT') or seq.startswith('GU')) and seq.endswith('AG')):
            return None
            
        try:
            # Calculate structure and energy
            structure, mfe = RNA.fold(seq)
            
            # Check delta G threshold
            if mfe >= delta_g_threshold:
                return None
            
            # Analyze patterns
            patterns = self.analyze_sequence_patterns(seq)
            
            return {
                'sequence': seq,
                'length': len(seq),
                'gc_content': (seq.count('G') + seq.count('C')) / len(seq) * 100,
                'delta_g': mfe,
                'structure': structure,
                '5_splice_site': patterns['splice_donor'],
                '3_splice_site': patterns['splice_acceptor'],
                'polypyrimidine_tract_score': patterns['polypyrimidine_tract']['score'],
                'branch_points': len(patterns['branch_points']),
                'enhancers': len(patterns['enhancers']),
                'silencers': len(patterns['silencers']),
                'gc_rich_regions': len(patterns['gc_rich_regions']),
                'pattern_analysis': patterns  # Store full pattern analysis
            }
        except:
            return None

    def analyze_sequence_patterns(self, seq: str) -> dict:
        """Analyze sequence patterns and motifs"""
        # Convert to uppercase and handle both DNA/RNA
        seq = seq.upper().replace('U', 'T')
        
        # Define common splicing motifs and regulatory elements
        branch_point_motifs = ['YNYTRAY', 'YNYYRAY', 'YNCTRAC']
        enhancer_motifs = ['GGAGG', 'YYYYYYYYYY']  # Polypyrimidine tract
        silencer_motifs = ['TCCTC', 'TGCATG']
        
        # Initialize patterns dictionary
        patterns = {
            'splice_donor': seq[:6],  # First 6 nucleotides
            'splice_acceptor': seq[-15:],  # Last 15 nucleotides
            'polypyrimidine_tract': {
                'sequence': seq[-15:-3],
                'score': (seq[-15:-3].count('C') + seq[-15:-3].count('T')) / 12  # Normalized score
            },
            'branch_points': [],
            'enhancers': [],
            'silencers': [],
            'gc_rich_regions': []
        }
        
        # Search for branch points
        for motif in branch_point_motifs:
            positions = self._find_motif_positions(seq, motif)
            if positions:
                patterns['branch_points'].extend([{
                    'position': pos,
                    'sequence': seq[pos:pos + len(motif)]
                } for pos in positions])
        
        # Search for enhancers
        for motif in enhancer_motifs:
            positions = self._find_motif_positions(seq, motif)
            if positions:
                patterns['enhancers'].extend([{
                    'position': pos,
                    'sequence': seq[pos:pos + len(motif)]
                } for pos in positions])
        
        # Search for silencers
        for motif in silencer_motifs:
            positions = self._find_motif_positions(seq, motif)
            if positions:
                patterns['silencers'].extend([{
                    'position': pos,
                    'sequence': seq[pos:pos + len(motif)]
                } for pos in positions])
        
        # Find GC-rich regions (window of 10 with >60% GC)
        window_size = 10
        for i in range(len(seq) - window_size + 1):
            window = seq[i:i + window_size]
            gc_content = (window.count('G') + window.count('C')) / window_size
            if gc_content > 0.6:
                patterns['gc_rich_regions'].append({
                    'position': i,
                    'sequence': window,
                    'gc_content': gc_content
                })
        
        return patterns

    def _find_motif_positions(self, seq: str, motif: str) -> list:
        """Helper function to find all positions of a motif in a sequence"""
        positions = []
        pos = 0
        while True:
            pos = seq.find(motif, pos)
            if pos == -1:
                break
            positions.append(pos)
            pos += 1
        return positions

    def process_genome_introns(self, 
                               window_size: int = 100,
                               step_size: int = 1,
                               sample_percentage: float = 100,
                               delta_g: float = -35,
                               min_intron_length: int = 50,
                               max_intron_length: int = 150):
        
        # Initialize UI elements
        progress_bar = st.progress(0)
        status_text = st.empty()
        stop_container = st.empty()
        
        # Initialize variables
        results = []
        processed = 0
        start_time = time.time()
        
        # Calculate total sequences
        seq_length = len(self.sequence)
        total_windows = (seq_length - window_size) // step_size
        if sample_percentage < 100:
            total_windows = int(total_windows * (sample_percentage / 100))
        
        st.write(f"Total sequences to analyze: {total_windows:,}")
        
        # Create stop button
        stop_button = stop_container.button("Stop Analysis", key="stop_analysis")
        
        # Process sequences
        for i in range(0, total_windows * step_size, step_size):
            if stop_button:
                if results:
                    df = pd.DataFrame(results)
                    st.session_state.results_df = df
                st.warning(f"Analysis stopped after processing {processed:,} sequences")
                return len(results), True
            
            # Get sequence window
            seq = self.sequence[i:i + window_size]
            
            # Analyze sequence
            result = self.analyze_sequence(seq, delta_g)
            if result is not None:
                results.append(result)
            
            # Update progress
            processed += 1
            if processed % 100 == 0:  # Update every 100 sequences
                progress = min(1.0, processed / total_windows)
                progress_bar.progress(progress)
                
                # Update status
                elapsed = time.time() - start_time
                remaining = (elapsed / processed) * (total_windows - processed)
                status_text.markdown(
                    f"""
                    Processed: {processed:,}/{total_windows:,} sequences ({progress*100:.1f}%)  
                    Structures found: {len(results):,}  
                    Time remaining: {remaining/3600:.1f} hrs  
                    Average Delta G: {np.mean([r['delta_g'] for r in results]) if results else 0:.2f}
                    """
                )
                
                # Save intermediate results
                if results:
                    st.session_state.results_df = pd.DataFrame(results)
        
        # Save final results
        if results:
            df = pd.DataFrame(results)
            st.session_state.results_df = df
            st.success(f"Analysis complete. Found {len(results)} structures.")
        
        return len(results), False

# Initialize analyzer
analyzer = GenomeAnalyzer()

# File upload section
uploaded_file = st.file_uploader(
    "Upload Genome File (FASTA format)", 
    type=['gz'],
    accept_multiple_files=False
)

# Analysis parameters
with st.form("analysis_parameters"):
    st.subheader("Analysis Parameters")
    col1, col2 = st.columns(2)
    
    with col1:
        window_size = st.number_input("Window Size", value=100, min_value=10)
        step_size = st.number_input("Step Size", value=1, min_value=1)
        sample_percentage = st.number_input("Sample Percentage", value=100.0, min_value=0.1, max_value=100.0)
    
    with col2:
        delta_g = st.number_input("Delta G Threshold", value=-35.0)
        min_intron_length = st.number_input("Min Intron Length", value=50)
        max_intron_length = st.number_input("Max Intron Length", value=150)
    
    submit_button = st.form_submit_button("Analyze Genome")

if uploaded_file is not None:
    if len(uploaded_file.getvalue()) > 1024 * 1024 * 1024:
        st.error("File is too large! Maximum size is 1GB")
    else:
        content = uploaded_file.read()
        try:
            analyzer.load_genome(content)
            st.success("Genome loaded successfully!")
        except Exception as e:
            st.error(f"Error loading genome: {str(e)}")

if submit_button and analyzer.sequence:
    try:
        st.write("Starting analysis...")
        
        # Create UI elements
        progress_bar = st.progress(0)
        status_text = st.empty()
        results_area = st.empty()
        
        sequences_processed, was_stopped = analyzer.process_genome_introns(
            window_size=window_size,
            step_size=step_size,
            sample_percentage=sample_percentage,
            delta_g=delta_g,
            min_intron_length=min_intron_length,
            max_intron_length=max_intron_length
        )
        
        # Update UI based on session state
        progress_bar.progress(st.session_state.progress)
        status_text.text(st.session_state.status)
        if st.session_state.current_findings is not None:
            with results_area:
                st.write("Current findings (showing last 5 sequences):")
                st.write(st.session_state.current_findings)
        
        if was_stopped or st.session_state.analysis_stopped:
            st.warning(f"Analysis stopped after processing {sequences_processed} sequences")
        else:
            st.success("Analysis complete!")
            
    except Exception as e:
        st.error(f"Error during analysis: {str(e)}")

# Add a separate section for results display that will persist
if st.session_state.results_df is not None:
    df = st.session_state.results_df
    
    if len(df) > 0:
        st.subheader("Analysis Results")
        st.write(f"Total sequences analyzed: {len(df)}")
        st.write(f"Average GC Content: {df['gc_content'].mean():.2f}%")
        st.write(f"GC Content Range: {df['gc_content'].min():.2f}% - {df['gc_content'].max():.2f}%")
        
        valid_folds = df['delta_g'].dropna()
        if len(valid_folds) > 0:
            st.write(f"Average Delta G: {valid_folds.mean():.2f}")
            st.write(f"Delta G Range: {valid_folds.min():.2f} to {valid_folds.max():.2f}")
        
        st.subheader("Results Table")
        st.dataframe(df)
        
        # Add download button
        st.download_button(
            label="Download Results CSV",
            data=df.to_csv(index=False).encode('utf-8'),
            file_name="genome_analysis_results.csv",
            mime="text/csv"
        )

# Add visualization section
st.subheader("Data Visualization")

if st.session_state.results_df is not None:
    df = st.session_state.results_df
    
    viz_type = st.selectbox(
        "Select Visualization",
        ["Distribution Plots", "Correlation Analysis", "Structure Browser", "Pattern Analysis"]
    )

    if len(df) > 0:
        if viz_type == "Distribution Plots":
            col1, col2 = st.columns(2)
            with col1:
                # GC Content Distribution
                fig_gc = px.histogram(df, x="gc_content", 
                                    title="GC Content Distribution",
                                    labels={"gc_content": "GC Content (%)"})
                st.plotly_chart(fig_gc)
            
            with col2:
                # Delta G Distribution
                fig_dg = px.histogram(df, x="delta_g", 
                                    title="Delta G Distribution",
                                    labels={"delta_g": "Delta G"})
                st.plotly_chart(fig_dg)
                
        elif viz_type == "Correlation Analysis":
            # Scatter plot of Length vs Delta G
            fig_corr = px.scatter(df, x="length", y="delta_g", 
                                color="gc_content",
                                title="Length vs Delta G (colored by GC Content)")
            st.plotly_chart(fig_corr)
            
        elif viz_type == "Structure Browser":
            # Interactive structure viewer
            selected_idx = st.selectbox("Select sequence to view", range(len(df)))
            selected_row = df.iloc[selected_idx]
            
            # Display structure visualization
            display_structure(
                selected_row['sequence'],
                selected_row['structure'],
                selected_row['delta_g']
            )
            
            # Additional structure information
            with st.expander("Additional Structure Information"):
                st.json({
                    'length': selected_row['length'],
                    'gc_content': selected_row['gc_content'],
                    'delta_g': selected_row['delta_g'],
                    '5_splice_site': selected_row['5_splice_site'],
                    '3_splice_site': selected_row['3_splice_site'],
                    'pattern_analysis': selected_row['pattern_analysis']
                })
        elif viz_type == "Pattern Analysis":
            if len(df) > 0:
                st.subheader("Sequence Pattern Analysis")
                
                # Summary statistics
                col1, col2 = st.columns(2)
                with col1:
                    st.write("5' Splice Site Consensus")
                    five_prime_counts = df['5_splice_site'].value_counts().head(10)
                    st.bar_chart(five_prime_counts)
                    
                with col2:
                    st.write("3' Splice Site Consensus")
                    three_prime_counts = df['3_splice_site'].value_counts().head(10)
                    st.bar_chart(three_prime_counts)
                
                # Polypyrimidine tract analysis
                st.write("Polypyrimidine Tract Score Distribution")
                fig_ppt = px.histogram(df, x='polypyrimidine_tract_score',
                                     title="Polypyrimidine Tract Score Distribution")
                st.plotly_chart(fig_ppt)
                
                # Pattern frequency analysis
                pattern_cols = ['branch_points', 'enhancers', 'silencers', 'gc_rich_regions']
                pattern_stats = pd.DataFrame({
                    'Average': df[pattern_cols].mean(),
                    'Max': df[pattern_cols].max(),
                    'Sequences with pattern (%)': (df[pattern_cols] > 0).mean() * 100
                })
                st.write("Pattern Statistics")
                st.dataframe(pattern_stats)
                
                # Detailed pattern viewer
                st.subheader("Detailed Pattern Viewer")
                selected_seq = st.selectbox("Select sequence to analyze", range(len(df)))
                if 'pattern_analysis' in df.columns:
                    patterns = df.iloc[selected_seq]['pattern_analysis']
                    st.json(patterns)
    else:
        st.warning("No data available for visualization. Please run the analysis first.")
else:
    st.warning("No results available. Please run the analysis first.")

# Add Statistical Analysis Section
st.subheader("Statistical Analysis")

if st.session_state.results_df is not None:
    df = st.session_state.results_df
    
    if len(df) > 0:
        # Create tabs for different types of analysis
        stats_tab, length_tab, motif_tab, energy_tab = st.tabs([
            "Basic Statistics", 
            "Length Analysis", 
            "Motif Statistics",
            "Energy Analysis"
        ])
        
        with stats_tab:
            st.write("### Distribution Metrics")
            
            # Check sample size before calculating statistics
            sample_size = len(df)
            
            if sample_size < 8:
                st.warning(f"Sample size too small for statistical analysis (n={sample_size}). Need at least 8 samples.")
            else:
                try:
                    # Basic statistics that don't require large sample sizes
                    numeric_cols = df.select_dtypes(include=[np.number]).columns
                    basic_stats = df[numeric_cols].agg(['mean', 'median', 'std']).fillna('N/A')
                    st.write("Basic Statistics:")
                    st.dataframe(basic_stats)
                    
                    # Advanced statistics that require larger sample sizes
                    if sample_size >= 20:
                        st.write("Advanced Statistics:")
                        # Calculate skewness and kurtosis
                        try:
                            skew_stats = df[numeric_cols].skew().fillna('N/A')
                            kurt_stats = df[numeric_cols].kurtosis().fillna('N/A')
                            
                            advanced_stats = pd.DataFrame({
                                'Skewness': skew_stats,
                                'Kurtosis': kurt_stats
                            })
                            st.dataframe(advanced_stats)
                        except Exception as e:
                            st.warning(f"Could not calculate advanced statistics: {str(e)}")
                    else:
                        st.info("Need at least 20 samples for advanced statistics "
                               f"(skewness and kurtosis). Current sample size: {sample_size}")
                    
                    # Normality test
                    if sample_size >= 8:
                        st.write("### Normality Test")
                        try:
                            stat, p_value = stats.normaltest(df['delta_g'].dropna())
                            st.write(f"D'Agostino's K^2 test p-value: {p_value:.4f}")
                            st.write("Interpretation: Data is " + 
                                    ("normally distributed" if p_value > 0.05 else "not normally distributed"))
                        except Exception as e:
                            st.warning(f"Could not perform normality test: {str(e)}")
                    
                    # Structure composition - Fixed version
                    st.write("### Structure Composition")
                    try:
                        # Calculate composition from the current sequence
                        composition = {
                            'G': df['sequence'].str.count('G').sum(),
                            'C': df['sequence'].str.count('C').sum(),
                            'A': df['sequence'].str.count('A').sum(),
                            'U': df['sequence'].str.count('U').sum()
                        }
                        if any(composition.values()):  # Check if we have any non-zero values
                            st.bar_chart(composition)
                            
                            # Add percentage breakdown
                            total_bases = sum(composition.values())
                            composition_pct = {
                                base: (count/total_bases * 100) 
                                for base, count in composition.items()
                            }
                            st.write("Base Composition Percentages:")
                            st.write(pd.Series(composition_pct).round(2).astype(str) + '%')
                        else:
                            st.warning("No composition data available")
                    except Exception as e:
                        st.warning(f"Could not display composition chart: {str(e)}")
                        
                except Exception as e:
                    st.error(f"Error calculating statistics: {str(e)}")
        
        with length_tab:
            st.write("### Sequence Length Analysis")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Length distribution plot
                fig_length = px.histogram(
                    df, 
                    x="length",
                    title="Sequence Length Distribution",
                    nbins=50
                )
                st.plotly_chart(fig_length)
                
                # Length statistics
                length_stats = {
                    'Mean Length': df['length'].mean(),
                    'Median Length': df['length'].median(),
                    'Mode Length': df['length'].mode().iloc[0],
                    'Standard Deviation': df['length'].std(),
                    'Coefficient of Variation': df['length'].std() / df['length'].mean()
                }
                st.write("Length Statistics:")
                st.write(pd.Series(length_stats))
            
            with col2:
                # Length vs GC content
                try:
                    fig_length_gc = px.scatter(
                        df,
                        x="length",
                        y="gc_content",
                        title="Length vs GC Content",
                        trendline="ols"
                    )
                except:
                    # Fallback without trendline if statsmodels is not available
                    fig_length_gc = px.scatter(
                        df,
                        x="length",
                        y="gc_content",
                        title="Length vs GC Content"
                    )
                st.plotly_chart(fig_length_gc)
                
                # Calculate correlation
                correlation = df['length'].corr(df['gc_content'])
                st.write(f"Correlation between Length and GC Content: {correlation:.3f}")
        
        with motif_tab:
            st.write("### Motif and Pattern Statistics")
            
            # Splice site analysis
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("#### 5' Splice Site Patterns")
                five_prime_patterns = df['5_splice_site'].value_counts()
                fig_5prime = px.pie(
                    values=five_prime_patterns.values,
                    names=five_prime_patterns.index,
                    title="5' Splice Site Distribution"
                )
                st.plotly_chart(fig_5prime)
            
            with col2:
                st.write("#### 3' Splice Site Patterns")
                three_prime_patterns = df['3_splice_site'].value_counts()
                fig_3prime = px.pie(
                    values=three_prime_patterns.values,
                    names=three_prime_patterns.index,
                    title="3' Splice Site Distribution"
                )
                st.plotly_chart(fig_3prime)
            
            # Pattern frequency analysis
            pattern_cols = ['branch_points', 'enhancers', 'silencers', 'gc_rich_regions']
            pattern_stats = pd.DataFrame({
                'Average Count': df[pattern_cols].mean(),
                'Median Count': df[pattern_cols].median(),
                'Max Count': df[pattern_cols].max(),
                'Sequences with Pattern (%)': (df[pattern_cols] > 0).mean() * 100
            })
            
            st.write("### Pattern Statistics")
            st.dataframe(pattern_stats)
            
            # Polypyrimidine tract analysis
            st.write("### Polypyrimidine Tract Analysis")
            fig_ppt = px.box(
                df,
                y='polypyrimidine_tract_score',
                title="Polypyrimidine Tract Score Distribution"
            )
            st.plotly_chart(fig_ppt)
        
        with energy_tab:
            st.write("### Energy Analysis")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Delta G distribution
                fig_delta_g = px.histogram(
                    df,
                    x="delta_g",
                    title="Delta G Distribution",
                    nbins=50
                )
                st.plotly_chart(fig_delta_g)
                
                # Energy statistics
                energy_stats = {
                    'Mean Delta G': df['delta_g'].mean(),
                    'Median Delta G': df['delta_g'].median(),
                    'Min Delta G': df['delta_g'].min(),
                    'Max Delta G': df['delta_g'].max(),
                    'Standard Deviation': df['delta_g'].std()
                }
                st.write("Energy Statistics:")
                st.write(pd.Series(energy_stats))
            
            with col2:
                # Delta G vs Length
                try:
                    fig_energy_length = px.scatter(
                        df,
                        x="length",
                        y="delta_g",
                        color="gc_content",
                        title="Delta G vs Length (colored by GC Content)",
                        trendline="ols"
                    )
                except:
                    # Fallback without trendline if statsmodels is not available
                    fig_energy_length = px.scatter(
                        df,
                        x="length",
                        y="delta_g",
                        color="gc_content",
                        title="Delta G vs Length (colored by GC Content)"
                    )
                st.plotly_chart(fig_energy_length)
                
                # Calculate correlations
                energy_corr = {
                    'Length vs Delta G': df['length'].corr(df['delta_g']),
                    'GC Content vs Delta G': df['gc_content'].corr(df['delta_g'])
                }
                st.write("Correlations:")
                st.write(pd.Series(energy_corr))
                
            # Add statistical tests
            st.write("### Statistical Tests")
            
            # Normality test for Delta G
            if len(df) >= 8:  # Only perform tests if we have enough samples
                try:
                    stat, p_value = stats.normaltest(df['delta_g'])
                    st.write(f"Normality Test for Delta G (D'Agostino's K^2 test):")
                    st.write(f"p-value: {p_value:.4f}")
                    st.write("Interpretation: Data is " + 
                            ("normally distributed" if p_value > 0.05 else "not normally distributed"))
                except Exception as e:
                    st.warning(f"Could not perform normality test: {str(e)}")
            else:
                st.warning("Need at least 8 samples to perform statistical tests. "
                           f"Current sample size: {len(df)}")
    
    else:
        st.warning("No data available for statistical analysis. Please run the analysis first.")
else:
    st.warning("No results available. Please run the analysis first.")

# Add a clear results button
if st.session_state.results_df is not None:
    if st.button("Clear Results", key="clear_results_button"):
        st.session_state.results_df = None
        st.session_state.analysis_stopped = False
        st.rerun()

def check_valid_numerical_data(df, column):
    """Check if a column has valid numerical data for statistical analysis"""
    valid_data = df[column].dropna()
    if len(valid_data) == 0:
        return False, "No valid numerical data available"
    if len(valid_data) < 8:
        return False, f"Need at least 8 valid samples (current: {len(valid_data)})"
    return True, valid_data

def main():
    try:
        st.title("RNA Inverse Folding")
        
        # Initialize session state
        if 'results' not in st.session_state:
            st.session_state.results = []
        
        # Input section
        with st.form("input_form"):
            sequence = st.text_input("Enter RNA sequence:", 
                                   help="Enter a valid RNA sequence (A, U, G, C)")
            target_structure = st.text_input("Enter target structure:",
                                           help="Enter target structure in dot-bracket notation")
            submitted = st.form_submit_button("Calculate")
        
        if submitted:
            if not sequence or not target_structure:
                st.warning("Please enter both sequence and target structure.")
                return
            
            if not is_valid_sequence(sequence):
                st.error("Invalid RNA sequence. Please use only A, U, G, C characters.")
                return
            
            if not is_valid_structure(target_structure):
                st.error("Invalid structure format. Please use dot-bracket notation.")
                return
            
            with st.spinner("Calculating inverse fold..."):
                result = calculate_inverse_fold(sequence, target_structure)
                if result:
                    st.session_state.results.append({
                        'sequence': sequence,
                        'structure': target_structure,
                        'result': result,
                        'timestamp': datetime.now()
                    })
        
        # Display results
        if st.session_state.results:
            st.subheader("Results")
            for idx, result in enumerate(reversed(st.session_state.results)):
                with st.expander(f"Result {idx + 1} - {result['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}"):
                    st.write(f"Sequence: {result['sequence']}")
                    st.write(f"Target Structure: {result['structure']}")
                    st.write(f"Inverse Fold Result: {result['result']}")
                    
                    # Plot structure
                    plot = plot_rna_structure(result['sequence'], result['structure'])
                    if plot:
                        st.image(plot, use_column_width=True)
    
    except Exception as e:
        logger.error(f"Application error: {str(e)}")
        st.error("An unexpected error occurred. Please try again later.")

if __name__ == "__main__":
    main()