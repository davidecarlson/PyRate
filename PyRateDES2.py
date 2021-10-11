#!/usr/bin/env python 
# Created by Daniele Silvestro on 04/04/2018 => pyrate.help@gmail.com 
import os,csv,platform
import argparse, os,sys, glob, time
import math
from numpy import *
import numpy as np
import scipy
import scipy.linalg
linalg = scipy.linalg
import scipy.stats
import random as rand
import nlopt
from scipy.integrate import odeint
from scipy.optimize import minimize

import multiprocessing, threading
import multiprocessing.pool
use_seq_lik = False
#try: 
#	import multiprocessing, thread
#	import multiprocessing.pool
#	use_seq_lik=False
#	if platform.system() == "Windows" or platform.system() == "Microsoft": use_seq_lik=True
#except(ImportError): 
#	print("\nWarning: library multiprocessing not found.\nPyRateDES will use (slower) sequential likelihood calculation. \n")
#	use_seq_lik=True

self_path=os.getcwd()

# DES libraries
self_path= os.path.dirname(sys.argv[0])
from importlib.machinery import SourceFileLoader

try: 
	self_path= os.path.dirname(sys.argv[0])
	des_model_lib = SourceFileLoader("des_model_lib", "%s/pyrate_lib/des_model_lib.py" % (self_path)).load_module()
	mcmc_lib = SourceFileLoader("mcmc_lib", "%s/pyrate_lib/des_mcmc_lib.py" % (self_path)).load_module()
	lib_DD_likelihood = SourceFileLoader("lib_DD_likelihood", "%s/pyrate_lib/lib_DD_likelihood.py" % (self_path)).load_module()
	lib_utilities = SourceFileLoader("lib_utilities", "%s/pyrate_lib/lib_utilities.py" % (self_path)).load_module()
except:
	self_path=os.getcwd()
	des_model_lib = SourceFileLoader("des_model_lib", "%s/pyrate_lib/des_model_lib.py" % (self_path)).load_module()
	mcmc_lib = SourceFileLoader("mcmc_lib", "%s/pyrate_lib/des_mcmc_lib.py" % (self_path)).load_module()
	lib_DD_likelihood = SourceFileLoader("lib_DD_likelihood", "%s/pyrate_lib/lib_DD_likelihood.py" % (self_path)).load_module()
	lib_utilities = SourceFileLoader("lib_utilities", "%s/pyrate_lib/lib_utilities.py" % (self_path)).load_module()

from des_model_lib import *
from mcmc_lib import *
from lib_DD_likelihood import *
from lib_utilities import *

np.set_printoptions(suppress=True) # prints floats, no scientific notation
np.set_printoptions(precision=3) # rounds all array elements to 3rd digit
small_number= 1e-5

citation= """\nThe DES method is described in:\nSilvestro, D., Zizka A., Bacon C. D., Cascales-Minana B. and Salamin, N., Antonelli, A. (2016)
Fossil Biogeography: A new model to infer dispersal, extinction and sampling from paleontological data.
Phil. Trans. R. Soc. B 371: 20150225.\n
"""


p = argparse.ArgumentParser() #description='<input file>') 

p.add_argument('-v',        action='version', version='%(prog)s')
p.add_argument('-cite',     help='print DES citation', action='store_true', default=False)
p.add_argument('-A',        type=int, help='algorithm - 0: parameter estimation, 1: TI, 2: ML, 3: ML with the subplex algorithm', default=0, metavar=0) # 0: par estimation, 1: TI
p.add_argument('-k',        type=int,   help='TI - no. scaling factors', default=10, metavar=10)
p.add_argument('-a',        type=float, help='TI - shape beta distribution', default=.3, metavar=.3)
p.add_argument('-hp',       help='Use hyper-prior on rates', action='store_true', default=False)
p.add_argument('-pw',       type=float, help='Exponent acceptance ratio (ML)', default=58, metavar=58) # accept 0.95 post ratio with 5% prob
p.add_argument('-seed',     type=int, help='seed (set to -1 to make it random)', default= 1, metavar= 1)
p.add_argument('-out',      type=str, help='output string',   default="", metavar="")

p.add_argument('-d',        type=str, help='input data set',   default="", metavar="<input file>")
p.add_argument('-n',        type=int, help='mcmc generations',default=100000, metavar=100000)
p.add_argument('-s',        type=int, help='sample freq.', default=100, metavar=100)
p.add_argument('-p',        type=int, help='print freq.',  default=100, metavar=100)
p.add_argument('-b',        type=int, help='burnin',  default=0)
p.add_argument('-thread',   type=int, help='no threads',  default=0)
p.add_argument('-A3set',    type=float, help='settings for -A 3 ML (stopping criteria: tolerance of parameters and likelihood, maximum iterations*1.25^K, maximum time (in s)) stepwise parameter optimization (1: yes, 0: no))',  default=[1e-2, 1e-4, 1000, 86400, 1], metavar=0, nargs='+')
p.add_argument('-A3init',   type=float,  help='initial values for maximum likelihood search',  default=[], metavar=0, nargs='+')
p.add_argument('-ver',      type=int, help='verbose',   default=0, metavar=0)
p.add_argument('-pade',     type=int, help='0) Matrix decomposition 1) Use Pade approx (slow)', default=0, metavar=0)
p.add_argument('-qtimes',   type=float, help='shift time (Q)',  default=[], metavar=0, nargs='+') # '*'
p.add_argument('-symd',     help='symmetric dispersal rates', action='store_true', default=False)
p.add_argument('-syme',     help='symmetric extinction rates', action='store_true', default=False)
p.add_argument('-symq',     help='symmetric preservation rates', action='store_true', default=False)
p.add_argument('-symCovD',   type=int,  help='symmetric correlations with dispersal (starting with 1 for 1st covariate in directory varD)',  default=[], metavar=0, nargs='+') # '*'
p.add_argument('-symCovE',   type=int,  help='symmetric correlations with extinction (starting with 1 for 1st covariate in directory varE)',  default=[], metavar=0, nargs='+') # '*'
p.add_argument('-constq',   type=int,  help='if 1 (or 2): constant q in area 1 (or 2)', default=0)
p.add_argument('-constr',   type=int, help='Contraints on covar parameters',  default=[], metavar=0, nargs='+') # '*'
#p.add_argument('-constA',   type=int, help='Contraints on covar parameters',  default=[], metavar=0, nargs='+') # '*'
p.add_argument('-data_in_area', type=int,  help='if data only in area 1 set to 1 (set to 2 if data only in area 2)', default=0)
p.add_argument('-varD',      type=str, help='Directory to time variable files for dispersal (takes all files)', default="", metavar="")
p.add_argument('-varE',      type=str, help='Directory to time variable files for dispersal (takes all files)', default="", metavar="")
p.add_argument('-r', type=float, help='rescale values (0 to scale in [0,1], 0.1 to reduce range 10x, 1 to leave unchanged)', default=0, metavar=0)
p.add_argument('-red',      type=int, help='if -red 1: reduce dataset to taxa with occs in both areas', default=0)
p.add_argument('-DivdD',    help='Use Diversity dependent Dispersal',  action='store_true', default=False)
p.add_argument('-DivdE',    help='Use Diversity dependent Extinction', action='store_true', default=False)
p.add_argument('-DdE',      help='Use Dispersal dependent Extinction', action='store_true', default=False)
p.add_argument('-DisdE',    help='Use Dispersal-rate dependent Extinction', action='store_true', default=False)
p.add_argument('-TdD',      help='Use Time dependent Dispersal',  action='store_true', default=False)
p.add_argument('-TdE',      help='Use Time dependent Extinction', action='store_true', default=False)
p.add_argument('-lgD',      help='Use logistic correlation Dispersal',  action='store_true', default=False)
p.add_argument('-lgE',      help='Use logistic correlation Extinction', action='store_true', default=False)
p.add_argument('-linE',      help='Use linear correlation Extinction', action='store_true', default=False)
p.add_argument('-cov_and_dispersal', help='Model with symmetric extinction covarying with both a proxy and dispersal', action='store_true', default=False)
#p.add_argument('-const', type=int, help='Constant d/e rate ()',default=0)
p.add_argument('-fU',     type=float, help='Tuning - update freq. (d, e, s)', default=[0, 0, 0], nargs=3)
p.add_argument("-mG", help='Model - Gamma heterogeneity of preservation rate', action='store_true', default=False)
p.add_argument("-ncat", type=int, help='Model - Number of categories for Gamma heterogeneity', default=4, metavar=4)
p.add_argument('-traitD', type=str, help='Trait file Dispersal', default="", metavar="")
p.add_argument('-traitE', type=str, help='Trait file Extinction', default="", metavar="")
p.add_argument('-logTraitD', type=str, help='Transform dispersal traits by taking logarithm 1) yes 0) no', default=1, metavar="", nargs='+')
p.add_argument('-logTraitE', type=str, help='Transform extinction traits by taking logarithm 1) yes 0) no', default=1, metavar="", nargs='+')
p.add_argument('-catD', type=str, help='Categorical file Dispersal (e.g. a trait or a clade)', default="", metavar="")
p.add_argument('-catE', type=str, help='Categorical file Extinction (e.g. a trait or a clade)', default="", metavar="")

### summary
p.add_argument('-sum',      type=str, help='Summarize results (provide log file)',  default="", metavar="log file")
p.add_argument('-plot', type=str, help='Marginal rates file or Log file for plotting covariate effect (the latter requires input data set, time variable files and model specification)', default="", metavar="")

### simulation settings ###
p.add_argument('-sim_d',  type=float, help='dispersal rates',  default=[.4, .1], metavar=1.1, nargs=2)
p.add_argument('-sim_e',  type=float, help='extinction rates', default=[.1, .05], metavar=.1, nargs=2)
p.add_argument('-sim_q',  type=float, help='preservation rates',   default=[1.,1.,], metavar=1, nargs=2)
p.add_argument('-i',      type=int,   help='simulation number',  default=0)
p.add_argument('-ran',    help='random settings', action='store_true', default=False)
p.add_argument('-t',      type=int, help='no taxa',  default=50, metavar=50)
# number of bins used to code the (simulated) geographic ranges
p.add_argument('-n_bins',  type=int, help='no bins',  default=20, metavar=20)
# number of bins to approximate continuous time DES process when simulating the data
p.add_argument('-n_sim_bins',  type=int, help='no bins for simulation',  default=1000,metavar=1000)
p.add_argument("-wd",        type=str, help='path to working directory', default="")

### generate DES input
p.add_argument('-fossil',   type=str, help='fossil occurrences', default="", metavar="")
p.add_argument('-recent',   type=str, help='recent distribution', default="", metavar="")
p.add_argument('-filename', type=str, help='input filename', default="", metavar="")
p.add_argument('-bin_size', type=float, help='size of the time bins', default=2.5, metavar=2.5)
p.add_argument('-rep',      type=int, help='replicates', default=1, metavar=1)
p.add_argument('-taxon',    type=str, help='taxon column within fossil', default="scientificName", metavar="")
p.add_argument('-area',     type=str, help='area column within fossil', default="higherGeography", metavar="")
p.add_argument('-age1',     type=str, help='earliest age', default="earliestAge", metavar="")
p.add_argument('-age2',     type=str, help='latest age', default="latestAge", metavar="")
p.add_argument('-trim_age', type=float, help='trim DES input to maximum age',  default=[])
p.add_argument('-plot_raw', help='plot raw diversity curves', action='store_true', default=False)

p.add_argument('-log_div', help='log modeled diversity (DivdD or DivdE models)', action='store_true', default=False)
p.add_argument('-log_dis', help='log modeled dispersal (DdE)', action='store_true', default=False)
p.add_argument('-log_distr', help='log estimated taxon distribution', action='store_true', default=False)
p.add_argument('-log_weights', help='log likelihood weights of the sampling categories (only -mG and -A 3)', action='store_true', default=False)

args = p.parse_args()
if args.cite is True:
	sys.exit(citation)
simulation_no = args.i

if args.seed==-1:
	rseed=np.random.randint(0,9999)
else: rseed=args.seed
random.seed(rseed)
np.random.seed(rseed)

print("Random seed: ", rseed)

# generate DES input
if args.fossil != "":
	reps = args.rep
	desin_list, time = des_in(args.fossil, args.recent, args.wd, args.filename, taxon = args.taxon, area = args.area, age1 = args.age1, age2 = args.age2, binsize = args.bin_size, reps = reps, trim_age = args.trim_age)
	if args.plot_raw:
		len_time = len(time)
		desin_div1 = np.zeros((reps, len_time))
		desin_div2 = np.zeros((reps, len_time))
		desin_div2 = np.zeros((reps, len_time))
		desin_div3 = np.zeros((reps, len_time))
		for i in range(reps):
			data_temp = desin_list[i]
			# area 1
			data_temp1 = 0.+data_temp
			data_temp1[data_temp1==2]=0
			data_temp1[data_temp1==3]=1
			desin_div1[i,:] = np.nansum(data_temp1,axis=0)
			# area 2
			data_temp2 = 0.+data_temp
			data_temp2[data_temp2==1]=0
			data_temp2[data_temp2==2]=1
			data_temp2[data_temp2==3]=1
			desin_div2[i,:] = np.nansum(data_temp2,axis=0)
			# both
			data_temp3 = 0.+data_temp
			data_temp3[data_temp3==1]=0
			data_temp3[data_temp3==2]=0
			data_temp3[data_temp3==3]=1
			desin_div3[i,:] = np.nansum(data_temp3,axis=0)
		desin_div1_mean = np.mean(desin_div1, axis = 0)
		desin_div2_mean = np.mean(desin_div2, axis = 0)
		desin_div3_mean = np.mean(desin_div3, axis = 0)
		desin_div1_hpd = np.zeros((2, len_time))
		desin_div2_hpd = np.zeros((2, len_time))
		desin_div3_hpd = np.zeros((2, len_time))
		desin_div1_hpd[:] = np.NaN
		desin_div2_hpd[:] = np.NaN
		desin_div3_hpd[:] = np.NaN
		if reps > 1:
			for i in range(len_time):
				par = desin_div1[:,i]
				desin_div1_hpd[:,i] = calcHPD(par, .95)
				par = desin_div2[:,i]
				desin_div2_hpd[:,i] = calcHPD(par, .95)
				par = desin_div3[:,i]
				desin_div3_hpd[:,i] = calcHPD(par, .95)
		# write R file
		print("\ngenerating R file...", end=' ')
		output_wd = args.wd
		name_file = os.path.splitext(os.path.basename(args.fossil))[0]
		out = "%s/%s_raw_div.r" % (output_wd, name_file)
		
		newfile = open(out, "w")
		if platform.system() == "Windows" or platform.system() == "Microsoft":
			wd_forward = os.path.abspath(output_wd).replace('\\', '/')
			r_script = "pdf(file='%s/%s_raw_div.pdf', width = 0.6*20, height = 0.6*10, useDingbats = FALSE)\n" % (wd_forward, name_file)
		else:
			r_script = "pdf(file='%s/%s_raw_div.pdf', width = 0.6*20, height = 0.6*10, useDingbats = FALSE)\n" % (output_wd, name_file)
		r_script += print_R_vec('\ntime', time)
		r_script += print_R_vec('\ndesin_div1_mean', desin_div1_mean)
		r_script += print_R_vec('\ndesin_div2_mean', desin_div2_mean)
		r_script += print_R_vec('\ndesin_div3_mean', desin_div3_mean)
		r_script += print_R_vec('\ndesin_div1_lwr', desin_div1_hpd[0,:])
		r_script += print_R_vec('\ndesin_div2_lwr', desin_div2_hpd[0,:])
		r_script += print_R_vec('\ndesin_div3_lwr', desin_div3_hpd[0,:])
		r_script += print_R_vec('\ndesin_div1_upr', desin_div1_hpd[1,:])
		r_script += print_R_vec('\ndesin_div2_upr', desin_div2_hpd[1,:])
		r_script += print_R_vec('\ndesin_div3_upr', desin_div3_hpd[1,:])
		r_script += "\nYlim = max(c(desin_div1_mean, desin_div2_mean, desin_div1_upr, desin_div2_upr), na.rm = TRUE)"
		r_script += "\nlayout(matrix(1:2, ncol = 2, nrow = 1, byrow = TRUE))"
		r_script += "\npar(las = 1, mar = c(4, 4, 0.5, 0.5))"
		r_script += "\nlen_time = length(time)"
		r_script += "\nslicer_1 = 1 + max(which(cumsum(desin_div1_mean) == 0))"
		r_script += "\ntime_1 = time[slicer_1:len_time]"
		r_script += "\ndesin_div1_mean = desin_div1_mean[slicer_1:len_time]"
		r_script += "\ndesin_div1_lwr = desin_div1_lwr[slicer_1:len_time]"
		r_script += "\ndesin_div1_upr = desin_div1_upr[slicer_1:len_time]"
		r_script += "\nslicer_2 = 1 + max(which(cumsum(desin_div2_mean) == 0))"
		r_script += "\ntime_2 = time[slicer_2:len_time]"
		r_script += "\ndesin_div2_mean = desin_div2_mean[slicer_2:len_time]"
		r_script += "\ndesin_div2_lwr = desin_div2_lwr[slicer_2:len_time]"
		r_script += "\ndesin_div2_upr = desin_div2_upr[slicer_2:len_time]"
		r_script += "\nslicer_3 = 1 + max(which(cumsum(desin_div3_mean) == 0))"
		r_script += "\ntime_3 = time[slicer_3:len_time]"
		r_script += "\ndesin_div3_mean = desin_div3_mean[slicer_3:len_time]"
		r_script += "\ndesin_div3_lwr = desin_div3_lwr[slicer_3:len_time]"
		r_script += "\ndesin_div3_upr = desin_div3_upr[slicer_3:len_time]"
		r_script += "\nplot(0, 0, type = 'n', ylim = c(0, Ylim), xlim = c(max(time), 0), xlab = 'Time', ylab = 'Diversity')"
		r_script += "\npolygon(c(time_1, rev(time_1)), c(desin_div1_lwr, rev(desin_div1_upr)), col = adjustcolor('dodgerblue', alpha = 0.3), border = NA)"
		r_script += "\npolygon(c(time_3, rev(time_3)), c(desin_div3_lwr, rev(desin_div3_upr)), col = adjustcolor('purple2', alpha = 0.3), border = NA)"
		r_script += "\nlines(time_1, desin_div1_mean, col = 'dodgerblue', lwd = 2)"
		r_script += "\nlines(time_3, desin_div3_mean, col = 'purple2', lwd = 2)"
		r_script += "\nlegend('topleft', legend = c('Diversity A', 'Diversity AB'), pch = c(15, 15), pt.cex = 1.5, col = adjustcolor(c('dodgerblue','purple2'), alpha = 0.3), bty = 'n')"
		r_script += "\nplot(0, 0, type = 'n', ylim = c(0, Ylim), xlim = c(max(time), 0), xlab = 'Time', ylab = 'Diversity')"
		r_script += "\npolygon(c(time_2, rev(time_2)), c(desin_div2_lwr, rev(desin_div2_upr)), col = adjustcolor('deeppink', alpha = 0.3), border = NA)"
		r_script += "\npolygon(c(time_3, rev(time_3)), c(desin_div3_lwr, rev(desin_div3_upr)), col = adjustcolor('purple2', alpha = 0.3), border = NA)"
		r_script += "\nlines(time_2, desin_div2_mean, col = 'deeppink', lwd = 2)"
		r_script += "\nlines(time_3, desin_div3_mean, col = 'purple', lwd = 2)"
		r_script += "\nlegend('topleft', legend = c('Diversity B', 'Diversity AB'), pch = c(15, 15), pt.cex = 1.5, col = adjustcolor(c('deeppink','purple2'), alpha = 0.3), bty = 'n')"
		r_script+="\ndev.off()"
		newfile.writelines(r_script)
		newfile.close()
		
		print("\nAn R script with the source for the RTT plot was saved as: %s_raw_div.r\n(in %s)" % (name_file, output_wd))
		if platform.system() == "Windows" or platform.system() == "Microsoft":
			cmd="cd %s & Rscript %s_%s_raw_div.r" % (output_wd, name_file, name_file)
		else:
			cmd="cd %s; Rscript %s/%s_raw_div.r" % (output_wd, output_wd, name_file)
		os.system(cmd)
		print("done\n")
	quit()


burnin= args.b
n_taxa= args.t
num_processes=args.thread
verbose= args.ver
n_bins= args.n_bins
n_sim_bins= args.n_sim_bins
sim_d_rate = np.array(args.sim_d)
sim_e_rate = np.array(args.sim_e)
q_rate = args.sim_q
nareas=2
sampling_prob_per_bin=q_rate
input_data= args.d
Q_times=np.sort(args.qtimes)
n_Q_times = len(Q_times)+1
output_wd = args.wd
if output_wd=="": output_wd= self_path

equal_d = args.symd
equal_e = args.syme
equal_q = args.symq
constraints_covar = np.array(args.constr)
constraints_covar_true = len(constraints_covar) > 0
constraints_01 = any(np.isin(constraints_covar, np.array([0, 1])))
constraints_23 = any(np.isin(constraints_covar, np.array([2, 3])))
constraints_45 = any(np.isin(constraints_covar, np.array([4, 5])))
d12_prior_idx = n_Q_times
d21_prior_idx = n_Q_times
e1_prior_idx = n_Q_times
e2_prior_idx = n_Q_times
if np.isin(0, constraints_covar): d12_prior_idx = 1
if np.isin(1, constraints_covar): d21_prior_idx = 1
if np.isin(2, constraints_covar): e1_prior_idx = 1
if np.isin(3, constraints_covar): e2_prior_idx = 1

const_q = args.constq
do_symCovD = False
symCovD = args.symCovD
if len(symCovD) > 0: do_symCovD = True
do_symCovE = False
symCovE = args.symCovE
if len(symCovE) > 0: do_symCovE = True
if args.cov_and_dispersal:
	model_DUO= 1
else: model_DUO= 0
argsG = args.mG
argsDdE = args.DdE
pp_gamma_ncat = args.ncat
rescale_factor=args.r
argstraitD = args.traitD
argstraitE = args.traitE
argscatD = args.catD
argscatE = args.catE

# if args.const==1:
# 	equal_d = True # this makes them symmatric not equal!
# 	equal_e = True # this makes them symmatric not equal!
# 	args.TdD = True
# 	args.TdE = True

### MCMC SETTINGS
if args.A ==2: 
	runMCMC = 0 # approximate ML estimation
	n_generations   = 100000
	if sum(args.fU)==0:
		update_freq     = [.4,.8,1]
	else: update_freq = args.fU
	sampling_freq   = 10
	max_ML_iterations = 5000
else: 
	runMCMC = 1
	n_generations   = args.n
	if sum(args.fU)==0:
		update_freq     = [.4,.8,1]
		if args.hp == True: 
			update_freq = [.3,.6,.9]
	else: update_freq = args.fU
	sampling_freq   = args.s

print_freq      = args.p
map_power       = args.pw
hp_alpha        = 2.
hp_beta         = 2.
use_Pade_approx = args.pade
scale_proposal  = 1

#### SUMMARIZE RESULTS
if args.sum !="":
	f=args.sum
	if burnin==0: 
		print("""Burnin was set to 0. Use command -b to specify a higher burnin
	(e.g. -b 100 will exclude the first 100 samples).""")
	t=loadtxt(f, skiprows=max(1,burnin))

	head = next(open(f)).split()
	start_column = 4
	j=0

	outfile=os.path.dirname(f)+"/"+os.path.splitext(os.path.basename(f))[0]+"_sum.txt"
	out=open(outfile, "wb")

	out.writelines("parameter\tmean\tmode\tHPDm\tHPDM\n")
	for i in range(start_column,len(head)-1):
		par = t[:,i]
		hpd = np.around(calcHPD(par, .95), decimals=3)
		mode = round(get_mode(par),3)
		mean_par = round(mean(par),3)
		if i==start_column: out_str= "%s\t%s\t%s\t%s\t%s\n" % (head[i], mean_par,mode,hpd[0],hpd[1])
		else: out_str= "%s\t%s\t%s\t%s\t%s\n" % (head[i], mean_par,mode,hpd[0],hpd[1])
		out.writelines(out_str)
		j+=1

	s= "\nA summary file was saved as: %s\n\n" % (outfile)
	sys.exit(s)

#### PLOT RATES THROUGH TIME
plot_file = args.plot
if plot_file != "":
	if "marginal_rates" in plot_file or "diversity" in plot_file or "dispersal" in plot_file:
		burnin = args.b

		if burnin == 0:
			print("""Burnin was set to 0. Use command -b to specify a higher burnin
(e.g. -b 100 will exclude the first 100 samples).""")
		rtt = loadtxt(plot_file, skiprows=max(1,burnin))
		mcmc_rtt = rtt.ndim == 2
		# No way to remove the TI steps
		if mcmc_rtt:
			ncols = shape(rtt)[1]
			hpd = np.zeros((2, ncols))
			for i in range(ncols):
				par = rtt[:,i]
				hpd[:,i] = calcHPD(par, .95)
			rate_mean = np.mean(rtt, axis = 0)
		else:
			ncols = shape(rtt)[0]
			hpd = np.zeros((2, ncols))
			hpd[:] = np.NaN
			rate_mean = rtt
		
		if "marginal_rates" in plot_file:
			idx1 = "d12"
			idx2 = "d21"
			r_file_name = "Dis_Ex_RTT"
			y_lab1 = "d12"
			y_lab2 = "d21"
			y_lab3 = "e1"
			y_lab4 = "e2"
			plot_size = 20
		if "diversity" in plot_file:
			idx1 = "div1"
			idx2 = "div2"
			r_file_name = "Diversity"
			y_lab1 = 'diversity 1'
			y_lab2 = 'diversity 2'
			plot_size = 10
		if "dispersal" in plot_file:
			idx1 = "dis12"
			idx2 = "dis21"
			r_file_name = "Dispersal"
			y_lab1 = 'dispersal 12'
			y_lab2 = 'dispersal 21'
			plot_size = 10
		head = next(open(plot_file)).split()
		d12_index = [head.index(i) for i in head if idx1 in i]
		d21_index = [head.index(i) for i in head if idx2 in i]
		d12_mean = rate_mean[d12_index]
		d21_mean = rate_mean[d21_index]
		d12_hpd = hpd[:,d12_index]
		d21_hpd = hpd[:,d21_index]

		if "marginal_rates" in plot_file:
			e1_index = [head.index(i) for i in head if "e1" in i]
			e2_index = [head.index(i) for i in head if "e2" in i]
			e1_mean = rate_mean[e1_index]
			e2_mean = rate_mean[e2_index]
			e1_hpd = hpd[:,e1_index]
			e2_hpd = hpd[:,e2_index]
		time_plot = []
		for i in d12_index:
			time_string = head[i].split("_")[1]
			time_plot.append(float(time_string))
		
		# write R file
		print("\ngenerating R file...", end=' ')
		output_wd = os.path.dirname(plot_file)
		name_file = os.path.splitext(os.path.basename(plot_file))[0]
		out = "%s/%s_%s.r" % (output_wd, name_file, r_file_name)
		
		newfile = open(out, "w")
		if platform.system() == "Windows" or platform.system() == "Microsoft":
			wd_forward = os.path.abspath(output_wd).replace('\\', '/')
			r_script = "pdf(file='%s/%s_%s.pdf', width = 0.6*20, height = 0.6*%s, useDingbats = FALSE)\n" % (wd_forward, name_file, r_file_name, plot_size)
		else:
			r_script = "pdf(file='%s/%s_%s.pdf', width = 0.6*20, height = 0.6*%s, useDingbats = FALSE)\n" % (output_wd, name_file, r_file_name, plot_size)
		r_script += print_R_vec('\ntime', time_plot)
		r_script += print_R_vec('\nd12_upr', d12_hpd[1,:])
		r_script += print_R_vec('\nd21_upr', d21_hpd[1,:])
		r_script += print_R_vec('\nd12_mean', d12_mean)
		r_script += print_R_vec('\nd21_mean', d21_mean)
		r_script += print_R_vec('\nd12_lwr', d12_hpd[0,:])
		r_script += print_R_vec('\nd21_lwr', d21_hpd[0,:])

		r_script += "\nYlim_d = max(c(d12_mean, d21_mean, d12_upr, d21_upr), na.rm = TRUE)"
		if "marginal_rates" in plot_file:
			r_script += "\nlayout(matrix(1:4, ncol = 2, nrow = 2, byrow = TRUE))"
		else:
			r_script += "\nlayout(matrix(1:2, ncol = 2, nrow = 1, byrow = TRUE))"
		r_script += "\npar(las = 1, mar = c(4, 4, 0.5, 0.5))"
		r_script += "\nplot(time, d12_mean, type = 'n', ylim = c(0, Ylim_d), xlim = c(max(time), 0), xlab = 'Time', ylab = '%s')" % (y_lab1)
		r_script += "\npolygon(c(time, rev(time)), c(d12_lwr, rev(d12_upr)), col = adjustcolor('#4c4cec', alpha = 0.3), border = NA)"
		r_script += "\nlines(time, d12_mean, col = '#4c4cec', lwd = 2)"
		r_script += "\nplot(time, d21_mean, type = 'n', ylim = c(0, Ylim_d), xlim = c(max(time), 0), xlab = 'Time', ylab = '%s')" % (y_lab2)
		r_script += "\npolygon(c(time, rev(time)), c(d21_lwr, rev(d21_upr)), col = adjustcolor('#4c4cec', alpha = 0.3), border = NA)"
		r_script += "\nlines(time, d21_mean, col = '#4c4cec', lwd = 2)"

		if "marginal_rates" in plot_file:
			r_script += print_R_vec('\ne1_upr', e1_hpd[1,:])
			r_script += print_R_vec('\ne2_upr', e2_hpd[1,:])
			r_script += print_R_vec('\ne1_mean', e1_mean)
			r_script += print_R_vec('\ne2_mean', e2_mean)
			r_script += print_R_vec('\ne1_lwr', e1_hpd[0,:])
			r_script += print_R_vec('\ne2_lwr', e2_hpd[0,:])
			r_script += "\nYlim_e = max(c(e1_mean, e2_mean, e1_upr, e2_upr), na.rm = TRUE)"
			r_script += "\nplot(time, e1_mean, type = 'n', ylim = c(0, Ylim_e), xlim = c(max(time), 0), xlab = 'Time', ylab = '%s')" % (y_lab3)
			r_script += "\npolygon(c(time, rev(time)), c(e1_lwr, rev(e1_upr)), col = adjustcolor('#e34a33', alpha = 0.3), border = NA)"
			r_script += "\nlines(time, e1_mean, col = '#e34a33', lwd = 2)"
			r_script += "\nplot(time, e2_mean, type = 'n', ylim = c(0, Ylim_e), xlim = c(max(time), 0), xlab = 'Time', ylab = '%s')" % (y_lab4)
			r_script += "\npolygon(c(time, rev(time)), c(e2_lwr, rev(e2_upr)), col = adjustcolor('#e34a33', alpha = 0.3), border = NA)"
			r_script += "\nlines(time, e2_mean, col = '#e34a33', lwd = 2)"
			r_script+="\ndev.off()"
		newfile.writelines(r_script)
		newfile.close()
		
		print("\nAn R script with the source for the RTT plot was saved as: %s_%s.r\n(in %s)" % (name_file, r_file_name, output_wd))
		if platform.system() == "Windows" or platform.system() == "Microsoft":
			cmd="cd %s & Rscript %s_%s_%s.r" % (output_wd, name_file, name_file, r_file_name)
		else:
			cmd="cd %s; Rscript %s/%s_%s.r" % (output_wd, output_wd, name_file, r_file_name)
		os.system(cmd)
		print("done\n")
		sys.exit("\n")


### INIT SIMULATION SETTINGS
# random settings
if args.ran is True:
	sim_d_rate = np.round(np.random.uniform(.025,.2, 2),2)
	sim_e_rate = np.round(np.random.uniform(0,sim_d_rate, 2),2)
	n_taxa = np.random.randint(20,75)
	q_rate = np.round(np.random.uniform(.05,1, 2),2)

print(sim_d_rate,sim_e_rate)

# sampling rates
TimeSpan = 23.25
sim_bin_size = TimeSpan/n_sim_bins
# 1 minus prob of no occurrences (Poisson waiting time) = prob of at least 1 occurrence [assumes homogenenous Poisson process]
# bin size:   [ 10.   5.    2.5   1.    0.5 ]
# q = 1.0   P=[ 1.    0.99  0.92  0.63  0.39]
# q = 0.5   P=[ 0.99  0.92  0.71  0.39  0.22]
# q = 0.1   P=[ 0.63  0.39  0.22  0.1   0.05]
#sampling_prob_per_bin = np.round(np.array([1-exp(-q_rate[0]*bin_size), 1-exp(-q_rate[1]*bin_size)]),2)
sampling_prob_per_sim_bin = np.array([1-exp(-q_rate[0]*sim_bin_size), 1-exp(-q_rate[1]*sim_bin_size)])

#########################################
######       DATA SIMULATION       ######
#########################################
if input_data=="":
	print("simulating data...")
	simulate_dataset(simulation_no,sim_d_rate,sim_e_rate,n_taxa,TimeSpan,n_sim_bins,output_wd)
	RHO_sampling = np.array(sampling_prob_per_sim_bin)
	time.sleep(1)
	input_data = "%s/sim_%s_%s_%s_%s_%s_%s.txt" % (output_wd,simulation_no,n_taxa,sim_d_rate[0],sim_d_rate[1],sim_e_rate[0],sim_e_rate[1]) 
	nTaxa, time_series, obs_area_series, OrigTimeIndex = parse_input_data(input_data,RHO_sampling,verbose,n_sampled_bins=n_bins)
	print(obs_area_series)
	len_time_series = len(time_series)
	sampled_sim = np.empty((nTaxa, len_time_series + 1))
	sampled_sim[:] = np.NaN
	sampled_sim[:, 0] = np.arange(nTaxa)
	for i in range(nTaxa):
		for y in range(len_time_series):
			if obs_area_series[i, y] == (nan,):
				obs = nan
			elif obs_area_series[i, y] == ():
				obs = 0
			elif obs_area_series[i, y] == (0,):
				obs = 1
				already_recorded = True
			elif obs_area_series[i, y] == (1,):
				obs = 2
				already_recorded = True
			elif obs_area_series[i, y] == (0,1):
				obs = 3
				already_recorded = True
			sampled_sim[i, y + 1] = obs
	# remove empty taxa (absent throughout)
	ind_keep = (np.nansum(sampled_sim[:,1:], axis=1) != 0).nonzero()[0]
	sampled_sim = sampled_sim[ind_keep]
	obs_area_series = obs_area_series[ind_keep]
	nTaxa = len(ind_keep)
	input_data = "%s/sim_samp_%s_%s_%s_%s_%s_%s.txt" % (output_wd,simulation_no,n_taxa,sim_d_rate[0],sim_d_rate[1],sim_e_rate[0],sim_e_rate[1])
	time_series = np.sort(time_series)[::-1]
	head_sampled_sim = "scientificName\t" + "\t".join(time_series.astype("str"))
	print(head_sampled_sim)
	np.savetxt(input_data, sampled_sim, delimiter="\t", header = head_sampled_sim, comments = '')
	if args.A==1: ti_tag ="_TI"
	else: ti_tag=""
	out_log = "%s/simContinuous_%s_b_%s_q_%s_mcmc_%s_%s_%s_%s_%s_%s_%s%s.log" \
	% (output_wd,simulation_no,n_bins,q_rate[0],n_taxa,sim_d_rate[0],sim_d_rate[1],sim_e_rate[0],sim_e_rate[1],q_rate[0],q_rate[1],ti_tag)
	out_rates ="%s/simContinuous_%s_b_%s_q_%s_mcmc_%s_%s_%s_%s_%s_%s_%s%s_marginal_rates.log" \
	% (output_wd,simulation_no,n_bins,q_rate[0],n_taxa,sim_d_rate[0],sim_d_rate[1],sim_e_rate[0],sim_e_rate[1],q_rate[0],q_rate[1],ti_tag)
	
else:
	print("parsing input data...")
	RHO_sampling= np.ones(2)
	nTaxa, time_series, obs_area_series, OrigTimeIndex = parse_input_data(input_data,RHO_sampling,verbose,n_sampled_bins=0,reduce_data=args.red)
#	OrigTimeIndex = np.ones(nTaxa, dtype = int)
	name_file = os.path.splitext(os.path.basename(input_data))[0]
	if len(Q_times)>0: Q_times_str = "_q_" + '_'.join(Q_times.astype("str"))
	else: Q_times_str=""
	if args.A==1: ti_tag ="_TI"
	else: ti_tag=""
	output_wd = os.path.dirname(input_data)
	if output_wd=="": output_wd= self_path
	model_tag=""
	if args.TdD: model_tag+= "_TdD"
	elif args.DivdD: model_tag+= "_DivdD"
	else: model_tag+= "_Dexp"
	if args.TdE: model_tag+= "_TdE"
	elif args.DivdE: model_tag+= "_DivdE"
	elif args.DisdE: model_tag+= "_DisdE"
	elif argsDdE: model_tag+= "_DdE"
	else: model_tag+= "_Eexp"

	if args.lgD: model_tag+= "_lgD"
	if args.lgE: model_tag+= "_lgE"
	if args.linE: model_tag+= "_linE"
	# constraints
	if equal_d is True: model_tag+= "_symd"
	if equal_e is True: model_tag+= "_syme"
	if equal_q is True: model_tag+= "_symq"
	if const_q > 0: model_tag+= "_constq%s" % (const_q)
	if runMCMC == 0: model_tag+= "_ML"
	if len(constraints_covar)>0:
		model_tag+= "_constr"
		for i in constraints_covar: model_tag+= "_%s" % (i)
	if do_symCovD:
		model_tag+= "_symCovD"
		for i in symCovD: model_tag+= "_%s" % (i)
	if do_symCovE:
		model_tag+= "_symCovE"
		for i in symCovE: model_tag+= "_%s" % (i)
	if argstraitD != "": model_tag+= "_TraitD"
	if argstraitE != "": model_tag+= "_TraitE"
	if argscatD != "": model_tag+= "_CatD"
	if argscatE != "": model_tag+= "_CatE"
	if argsG is True: model_tag+= "_G"
	if args.A == 3: model_tag+= "_Mlsbplx"
		
	out_log ="%s/%s_%s%s%s%s%s.log" % (output_wd,name_file,simulation_no,Q_times_str,ti_tag,model_tag,args.out)
	out_rates ="%s/%s_%s%s%s%s%s_marginal_rates.log" % (output_wd,name_file,simulation_no,Q_times_str,ti_tag,model_tag,args.out)
	time_series = np.sort(time_series)[::-1] # the order of the time vector is only used to assign the different Q matrices
	                                         # to the correct time bin. Q_list[0] = root age, Q_list[n] = most recent

if verbose ==1: 
	print(time_series)
	print(obs_area_series)
	
#############################################
######            INIT MODEL           ######
#############################################
print("initializing model...")
delta_t= abs(np.diff(time_series))
bin_size = delta_t[0]
possible_areas= list(powerset(np.arange(nareas)))

tbl = np.genfromtxt(input_data, dtype=str, delimiter='\t')
tbl_temp=tbl[1:,1:]
data_temp=tbl_temp.astype(float)
# remove empty taxa (absent throughout)
ind_keep = (np.nansum(data_temp,axis=1) != 0).nonzero()[0]
data_temp = data_temp[ind_keep]

# For the one area model, we need to identify the bin of the last appearance in the focal area
# Also useful in the two area case if we know the exact time and area (!) of extinction
bin_last_occ = np.zeros(nTaxa, dtype = int)
len_delta_t = len(delta_t)
present_data = np.empty(nTaxa, dtype = object)
for i in range(nTaxa):
	last_occ = np.max( np.where( np.in1d(data_temp[i,:], [0., 1., 2., 3.]) ) )
	bin_last_occ[i] = last_occ
	present_data[i] = obs_area_series[i, last_occ]
print("last occurrence bin", bin_last_occ)
print("present data", present_data)

rho_at_present_LIST=[]
r_vec_indexes_LIST=[]
sign_list_LIST=[]


list_taxa_index =[]
for l in range(nTaxa):
	rho_at_present=np.zeros(len(possible_areas))
	try: 
		rho_at_present[possible_areas.index(present_data[l])]=1 # assign prob 1 for observed range at present, 0 for all others
		list_taxa_index.append(l)
	except: rho_at_present=np.zeros(len(possible_areas)) # NaN at present (entire species not preserved)
	rho_at_present_LIST.append(rho_at_present)
	# INIT PARMS
	r_vec_indexes,sign_list=build_list_rho_index_vec(obs_area_series[l],nareas,possible_areas)
	r_vec_indexes_LIST.append(r_vec_indexes)
	sign_list_LIST.append(sign_list)
#####	

#dis_rate_vec= np.array([.1,.1]  ) #__ np.zeros(nareas)+.5 # np.random.uniform(0,1,nareas)
#ext_rate_vec= np.array([.005,.005]) #__ np.zeros(nareas)+.05 # np.random.uniform(0,1,nareas)
#r_vec= np.array([0]+list(np.zeros(nareas)+0.001) +[1])
# where r[1] = prob not obs in A; r[2] = prob not obs in B
# r[0] = 0 (for impossible ranges); r[3] = 1 (for obs ranges)





scal_fac_TI=np.ones(1)
if args.A==1:
	# parameters for TI are currently hard-coded (K=10, alpha=0.3)
	scal_fac_TI=get_temp_TI(args.k,args.a)



#############################################
######       MULTIPLE Q MATRICES       ######
#############################################
"""
Q_list = [Q1,Q2,...]
Q_index = [0,0,0,1,1,1,1,....] # Q index for each time bin
so that at time t: Q = Q_list[t]

d= [[d1,d2]
    [d1,d2]
    ......
           ]
NOTE that Q_list[0] = root age, Q_list[n] = most recent
"""

# INIT PARAMETERS
dis_rate_vec=np.random.uniform(0.1,0.2,nareas*1).reshape(1,nareas)
if args.TdD: 
	dis_rate_vec=np.random.uniform(0.05,0.15,nareas*n_Q_times).reshape(n_Q_times,nareas)
	#dis_rate_vec = np.array([0.194,0.032,0.007,0.066,0.156,0.073]).reshape(n_Q_times,nareas)
ext_rate_vec=np.random.uniform(0.01,0.05,nareas*1).reshape(1,nareas)
if args.TdE: 
	ext_rate_vec=np.random.uniform(0.01,0.05,nareas*n_Q_times).reshape(n_Q_times,nareas)
	#ext_rate_vec = np.array([0.222,0.200,0.080,0.225,0.216,0.435]).reshape(n_Q_times,nareas)
if equal_d is True:
	d_temp=dis_rate_vec[:,0]
	dis_rate_vec = array([d_temp,d_temp]).T
if equal_e is True:
	e_temp=ext_rate_vec[:,0]
	ext_rate_vec = array([e_temp,e_temp]).T

r_vec= np.zeros((n_Q_times,nareas+2)) 
r_vec[:,1:3]=0.25
r_vec[:,3]=1
#q_rate_vec = np.array([0.317,1.826,1.987,1.886,2.902,2.648])
#r_vec_temp  = exp(-q_rate_vec*bin_size).reshape(n_Q_times,nareas)
#r_vec[:,1:3]=r_vec_temp





# where r[1] = prob not obs in A; r[2] = prob not obs in B
# r[0] = 0 (for impossible ranges); r[3] = 1 (for obs ranges)
#for i in range(len(time_series)):
ind_shift=[]

for i in Q_times: ind_shift.append(np.argmin(abs(time_series-i)))

ind_shift.append(len(time_series))
ind_shift= np.sort(ind_shift)[::-1]
# Q_index = [0,0,0,1,1,1,1,....] # Q index for each time bin
# Note that Q_index also provides the index for r_vec
if verbose ==1: print(ind_shift,time_series)
Q_index=np.zeros(len(time_series))
i,count=0,0
for j in ind_shift[::-1]:
	print(i, j, count)
	Q_index[i:j]=count
	i=j
	count+=1

Q_index =Q_index.astype(int) 
if verbose ==1: print(Q_index, shape(dis_rate_vec))

prior_exp_rate = 1.

data_in_area = args.data_in_area
if data_in_area == 1:
	ext_rate_vec[:,1] = 0
	dis_rate_vec[:,0] = 0
	r_vec[:,2] = small_number
elif data_in_area == 2:
	ext_rate_vec[:,0] = 0
	dis_rate_vec[:,1] = 0
	r_vec[:,1] = small_number

print(np.shape(ext_rate_vec))

YangGammaQuant = array([1.])
if argsG is True:
	YangGammaQuant = (np.linspace(0,1,pp_gamma_ncat+1)-np.linspace(0,1,pp_gamma_ncat+1)[1]/2)[1:]
alpha = array([10.]) # little sampling heterogeneity 

#############################################
######               MCMC              ######
#############################################

print("data size:", len(list_taxa_index), nTaxa, len(time_series))

print("starting MCMC...")
#if use_seq_lik is True: num_processes=0
#if num_processes>0: pool_lik = multiprocessing.Pool(num_processes) # likelihood
start_time=time.time()

update_rate_freq_d = max(0.1, 1.5/sum(np.size(dis_rate_vec)))
update_rate_freq_e = max(0.1, 1.5/sum(np.size(ext_rate_vec)))
update_rate_freq_r = max(0.1, 1.5/sum(np.size(r_vec)))
print("Origination time (binned):", OrigTimeIndex, delta_t) # update_rate_freq, update_freq
l=1
recursive = np.arange(OrigTimeIndex[l],len(delta_t))[::-1]
print(recursive)
print(shape(r_vec_indexes_LIST[l]),shape(sign_list_LIST[l]))
#quit()

# EMPIRICAL INIT EANA

#dis_rate_vec=np.array([0.014585816,0.019537033,0.045284283,0.011647877,0.077365681,0.072545101]).reshape(n_Q_times,nareas)
#    q_rate_vec = np.array([1.581652245,1.517955917 ,1.601288529 ,1.846235859 ,2.664323002 ,3.438584756])
#    r_vec_temp  = exp(-q_rate_vec*bin_size).reshape(n_Q_times,nareas)
#    r_vec[:,1:3]=r_vec_temp
#    
#    # start for TempD TempE
#    ext_rate_vec = np.array([0.121 , 0.121]).reshape(1,nareas)
#    dis_rate_vec = np.array([.053 , .053]).reshape(1,nareas)
#    covar_par_A = np.array([-0.0118503199,-0.0118503199,-0.104669685,-0.104669685])
#    
#    ## start for TempD DdE
#    # ./PyRateDES2.py -d /Users/danielesilvestro/Documents/Projects/DES_II/Carnivora/Carnivora_raw_data/neogene/EANAng3/EANAng3_rep1.txt -var /Users/danielesilvestro/Documents/Projects/DES_II/Carnivora/Carnivora_raw_data/neogene/NeogeneTempSmooth.txt -qtimes 5.3 2.6 -DdE -symCov 1 -A 2 -symd
#    #ext_rate_vec = np.array([0.043327715,0.127886299]).reshape(1,nareas)
#    #ext_rate_vec = np.array([0.12,0.12]).reshape(1,nareas)
#    #dis_rate_vec = np.array([.05,.05]).reshape(1,nareas)
#    #covar_par_A = np.array([-0.15,-0.15,0.279991284,0.070409858])
#    covar_par_A = np.array([-0.011 ,-0.011 ,0 , 0])
#    ext_rate_vec=np.array([0.151 , 0.151 , 0.159 , 0.159 , 0.327 , 0.327]).reshape(n_Q_times,nareas)
#
#	d: [ 0.096  0.096] e: [ 0.121  0.121] q: [ 1.603  1.513  1.61   1.785  2.634  3.465]
#	a/k: [-0.022 -0.022  0.143  0.143] x0: [ 0.  0.  0.  0.]
#	d: [ 0.053  0.053] e: [ 0.151  0.151  0.159  0.159  0.327  0.327] q: [ 1.598  1.521  1.595  1.757  2.688  3.455]
#	a/k: [-0.011 -0.011  0.     0.   ] x0: [ 0.  0.  0.  0.]



#-0.009073347	-0.138451368	-0.062747722	-0.059015597
#dis_rate_vec=np.array([0.014585816,0.019537033,0.045284283,0.011647877,0.077365681,0.072545101]).reshape(n_Q_times,nareas)
#q_rate_vec = np.array([0.32033397,1.958145806,1.948256733,1.835880139,2.542124041,2.720067697])
#r_vec_temp  = exp(-q_rate_vec*bin_size).reshape(n_Q_times,nareas)
#r_vec[:,1:3]=r_vec_temp
#
#dis_rate_vec=np.array([.18,.05,.18,0.1,.18,.05]).reshape(n_Q_times,nareas)
#ext_rate_vec = np.array([0.25,0.25]).reshape(1,nareas)
##dis_rate_vec = np.array([.18,.05]).reshape(1,nareas)
#covar_par_A = np.array([0,0,-0.05,-0.05])
#





#############################################
#####    time variable Q (no shifts)    #####
#############################################
#try:
#	time_var_temp = get_binned_continuous_variable(time_series, args.varD)
#	# SHIFT TIME VARIABLE ()
#	time_var = time_var_temp-time_var_temp[len(delta_t)-1]
#	print "Rescaled variable",time_var, time_series
#	if args.varE=="":
#		time_varE=time_var		
#	else:
#		## TEMP FOR EXTINCTION
#		time_var_temp = get_binned_continuous_variable(time_series, args.varE)
#		# SHIFT TIME VARIABLE ()
#		time_varE = time_var_temp-time_var_temp[len(delta_t)-1]
#		
#except:
#	time_var = np.ones(len(time_series)-1)
#	print "Covariate-file not found"
def rescale_and_center_time_var(time_var, rescale_factor):
	unscaled_min = np.min(time_var)
	unscaled_max = np.max(time_var)
	unscaled_mean = np.mean(time_var)
	if rescale_factor > 0:
		time_var = time_var * rescale_factor
	else:
		denom = np.max(time_var) - np.min(time_var)
		if denom==0: denom=1.
		time_var = time_var/denom
		time_var = time_var - np.min(time_var) # curve rescaled between 0 and 1
	mean_before_centering = np.mean(time_var)
	time_var = time_var - mean_before_centering
	return time_var, mean_before_centering, unscaled_min, unscaled_max, unscaled_mean

mean_varD_before_centering = np.zeros(1)
mean_varE_before_centering = np.zeros(1)
# if args.varD != "" and args.varE != "":
# 	time_var_temp = get_binned_continuous_variable(time_series, args.varD)
# 	time_varD, mean_varD_before_centering, time_varD_unscmin, time_varD_unscmax, time_varD_unscmean = rescale_and_center_time_var(time_var_temp, rescale_factor)
# 	print("Rescaled variable dispersal",time_varD, time_series)
# 	covar_mean_dis = np.mean(time_varD)
# 	time_var_temp = get_binned_continuous_variable(time_series, args.varE)
# 	time_varE, mean_varE_before_centering, time_varE_unscmin, time_varE_unscmax, time_varE_unscmean = rescale_and_center_time_var(time_var_temp, rescale_factor)
# 	print("Rescaled variable extinction",time_varE, time_series)
# 	covar_mean_ext = np.mean(time_varE)
time_varD = np.ones((len(time_series) - 1, 1))
time_varE = np.ones((len(time_series) - 1, 1))
do_varD = False
if args.varD != "": do_varD = True
do_varE = False
if args.varE != "": do_varE = True
if do_varD:
	all_dis_files = "%s/*" % (args.varD)
	list_dis_files = list(sort(glob.glob(all_dis_files)))
	num_dis_files = len(list_dis_files)
	time_varD = np.ones((len(time_series) - 1, num_dis_files))
	mean_varD_before_centering = np.zeros(num_dis_files)
	time_varD_unscmin = np.ones(num_dis_files)
	time_varD_unscmax = np.ones(num_dis_files)
	time_varD_unscmean = np.ones(num_dis_files)
	for i in range(num_dis_files):
		time_var_temp = get_binned_continuous_variable(time_series, list_dis_files[i])
		time_varD[:,i], mean_varD_before_centering[i], time_varD_unscmin[i], time_varD_unscmax[i], time_varD_unscmean[i] = rescale_and_center_time_var(time_var_temp, rescale_factor)
#		print("Rescaled variable dispersal",time_varD, time_series)
	covar_mean_dis = np.mean(time_varD, axis = 0)
	mean_varD_before_centering = mean_varD_before_centering
if do_varE:
	all_ext_files = "%s/*" % (args.varE)
	list_ext_files = list(sort(glob.glob(all_ext_files)))
	num_ext_files = len(list_ext_files)
	time_varE = np.ones((len(time_series) - 1, num_ext_files))
	mean_varE_before_centering = np.zeros(num_ext_files)
	time_varE_unscmin = np.ones(num_ext_files)
	time_varE_unscmax = np.ones(num_ext_files)
	time_varE_unscmean = np.ones(num_ext_files)
	for i in range(num_ext_files):
		time_var_temp = get_binned_continuous_variable(time_series, list_ext_files[i])
		time_varE[:,i], mean_varE_before_centering[i], time_varE_unscmin[i], time_varE_unscmax[i], time_varE_unscmean[i] = rescale_and_center_time_var(time_var_temp, rescale_factor)
#		print("Rescaled variable extinction",time_varE, time_series)
	covar_mean_ext = np.mean(time_varE, axis = 0)

#mean_varD_before_centering = np.array([mean_varD_before_centering, mean_varD_before_centering])
#mean_varE_before_centering = np.array([mean_varE_before_centering, mean_varE_before_centering])
mean_varD_before_centering = np.concatenate((mean_varD_before_centering, mean_varD_before_centering))
mean_varE_before_centering = np.concatenate((mean_varE_before_centering, mean_varE_before_centering))
bound_covar = 25.
range_time_varD = np.max(time_varD, axis = 0) - np.min(time_varD, axis = 0)
range_time_varE = np.max(time_varE, axis = 0) - np.min(time_varE, axis = 0)
bound_covar_d = (1. + small_number) / (range_time_varD + small_number) * bound_covar
bound_covar_e = (1. + small_number) / (range_time_varE + small_number) * bound_covar
num_varD = time_varD.shape[1]
num_varE = time_varE.shape[1]
covar_parD_A = np.zeros(2 * num_varD)
covar_parE_A = np.zeros(2 * num_varE)
x0_logisticD_A = np.zeros(2 * num_varD)
x0_logisticE_A = np.zeros(2 * num_varD)
covar_par_A = np.zeros(4)


def get_idx_symCov(symCov, num_var):
	sym_cov_idx = list()
	counter = 0
	for i in range(2 * num_var):
		if ((i + 1)/2 in symCov) is False:
			sym_cov_idx.append(counter)
			counter += 1
		else:
			counter -= 1
			sym_cov_idx.append(counter)
			counter += 1
	return np.array(sym_cov_idx)


if do_varD:
	idx2_symCovD = np.arange(0, 2 * num_varD, 1)
	if do_symCovD:
		idx_symCovD = get_idx_symCov(symCovD, num_varD)
		idx2_symCovD = idx2_symCovD[np.isin(idx2_symCovD, 2 * np.array(symCovD) - 1) == False]
else:
	idx2_symCovD = np.array([0, 1])
	if do_symCovD:
		idx_symCovD = np.zeros(2, dtype = int)
		idx2_symCovD = np.zeros(1, dtype = int)
if do_varE:
	idx2_symCovE = np.arange(0, 2 * num_varD, 1)
	if do_symCovE:
		idx_symCovE = get_idx_symCov(symCovE, num_varE)
		idx2_symCovE = idx2_symCovE[np.isin(idx2_symCovE, 2 * np.array(symCovE) - 1) == False]
else:
	idx2_symCovE = np.array([0, 1])
	if do_symCovE:
		idx_symCovE = np.zeros(2, dtype = int)
		idx2_symCovE = np.zeros(1, dtype = int)

if args.DivdD:
	covar_par_A[0:2] = np.array([nTaxa * 1., nTaxa * 1.])
if args.DivdE:
	covar_par_A[2:4] = np.array([nTaxa * 1., nTaxa * 1.])
x0_logistic_A =np.zeros(4)
#x0_logistic_A = np.array([np.mean(time_varD), np.mean(time_varD), np.mean(time_varE), np.mean(time_varE)])

# Traits
def read_trait(path_var, taxa_input):
	var = np.loadtxt(path_var, dtype = str, delimiter = '\t', skiprows = 1)
	# Filter and sort for the species in the input file - there should be no missing trait data
	idx = []
	for ta in taxa_input:
		pos = np.where(var[:,0] == ta)[0].tolist()
		idx.append(pos)
	idx = np.array(idx).flatten()
	var = var[idx,:]
	var_shape = var.shape
	var = np.reshape(var[:,1:], (var_shape[0], var_shape[1] - 1))
	var = var.astype(float)
	return var


def logtransf_traits(var, transfTrait):
	num_traitD = var.shape[1]
	transfTrait = transfTrait.astype(bool)
	var = np.log(var, where = transfTrait)
	var = var - np.mean(var, axis = 0)
	return var


taxa_input = tbl[1:,0][ind_keep]
traitD = np.ones((len(taxa_input), 1))
traitE = np.ones((len(taxa_input), 1))
traits = False
if argstraitD != "":
	traitD = read_trait(argstraitD, taxa_input)
	traitD_untrans = traitD
	traitD = logtransf_traits(traitD, np.array(args.logTraitD))
	traits = True
num_traitD = traitD.shape[1]
trait_parD_A = np.zeros(num_traitD)
if argstraitE != "":
	traitE = read_trait(argstraitE, taxa_input)
	traitE_untrans = traitE
	traitE = logtransf_traits(traitE, np.array(args.logTraitE))
	traits = True
num_traitE = traitE.shape[1]
trait_parE_A = np.zeros(num_traitE)

range_traitD = np.max(traitD, axis = 0) - np.min(traitD, axis = 0)
range_traitE = np.max(traitE, axis = 0) - np.min(traitE, axis = 0)
bound_traitD = (1. + small_number) / (range_traitD + small_number) * bound_covar
bound_traitE = (1. + small_number) / (range_traitE + small_number) * bound_covar

# Categories
catD = np.zeros((len(taxa_input), 1), dtype = int)
catE = np.zeros((len(taxa_input), 1), dtype = int)
num_catD = np.zeros(1, dtype = int)
num_catE = np.zeros(1, dtype = int)
cat_parD_idx = list()
cat_parD_idx.append(np.zeros(1, dtype = int))
cat_parE_idx = list()
cat_parE_idx.append(np.zeros(1, dtype = int))
cat = False
catD_baseline = np.zeros(1, dtype = int) # Most frequent state will be the baseline in ML
catE_baseline = np.zeros(1, dtype = int)
if argscatD != "":
	catD = read_trait(argscatD, taxa_input)
	catD = catD - np.min(catD, axis = 0)
	num_catD = np.max(catD, axis = 0).astype(int)
	catD = catD + np.concatenate((np.zeros(1), np.cumsum(num_catD + 1)[:-1]))
	catD = catD.astype(int)
	freq_catD = np.unique(catD, return_counts = True)[1]
	cat_parD_idx = list()
	catD_baseline = np.zeros(len(num_catD)).astype(int)
	for i in range(len(num_catD)):
		cat_parD_idx_i = np.unique(catD[:, i])
		cat_parD_idx.append(cat_parD_idx_i)
		catD_baseline[i] = cat_parD_idx_i[np.argmax(freq_catD[cat_parD_idx_i])]
	cat = True
if argscatE != "":
	catE = read_trait(argscatE, taxa_input)
	catE = catE - np.min(catE, axis = 0)
	num_catE = np.max(catE, axis = 0).astype(int)
	catE = catE + np.concatenate((np.zeros(1), np.cumsum(num_catE + 1)[:-1]))
	catE = catE.astype(int)
	freq_catE = np.unique(catE, return_counts = True)[1]
	cat_parE_idx = list()
	catE_baseline = np.zeros(len(num_catE)).astype(int)
	for i in range(len(num_catE)):
		cat_parE_idx_i = np.unique(catE[:, i])
		cat_parE_idx.append(cat_parE_idx_i)
		catE_baseline[i] = cat_parE_idx_i[np.argmax(freq_catE[cat_parE_idx_i])]
	cat = True
unique_catD = np.unique(catD)
unique_catE = np.unique(catE)
#cat_parD_A = np.ones(np.sum(num_catD) + len(num_catD))
#cat_parE_A = np.ones(np.sum(num_catE) + len(num_catE))
cat_parD_A = np.zeros(len(unique_catD))
cat_parE_A = np.zeros(len(unique_catE))
catD_not_baseline = np.isin(np.arange(0, len(unique_catD)), catD_baseline) == False
catE_not_baseline = np.isin(np.arange(0, len(unique_catE)), catE_baseline) == False
hp_catD_A = np.ones(1)
hp_catE_A = np.ones(1)
#if args.A != 3: # Bayesian infers deviation from a common mean while ML baseline + state specific multiplier
#	catD_baseline = np.repeat(False, len(unique_catD))
#	catE_baseline = np.repeat(False, len(unique_catE))

# DIVERSITY TRAJECTORIES
# area 1
data_temp1 = 0.+data_temp
data_temp1[data_temp1==2]=0
data_temp1[data_temp1==3]=1
div_traj_1 = np.nansum(data_temp1,axis=0)[0:-1]

# area 2
data_temp2 = 0.+data_temp
data_temp2[data_temp2==1]=0
data_temp2[data_temp2==2]=1
data_temp2[data_temp2==3]=1
div_traj_2 = np.nansum(data_temp2,axis=0)[0:-1]
print("Diversity trajectories", div_traj_1,div_traj_2)

#def smooth_trajectory(div_traj):
#	for i in range(len(div_traj)):
#		j=len(a)-i-1
#		print j, a[j]

# Get area and time for the first record of each species
# Could there be area 0? The example data have this but why?
bin_first_occ = np.zeros(nTaxa, dtype = int)
first_area = np.zeros(nTaxa)
first_time = np.zeros(nTaxa)
for i in range(nTaxa):
	bin_first_occ[i] = np.min( np.where( np.in1d(data_temp[i,:], [1., 2., 3.]) ) )
	first_area[i] = data_temp[i, bin_first_occ[i]]
	first_time[i] = time_series[bin_first_occ[i]]
	
#print "First bin", bin_first_occ
#print "First area", first_area
#print "First time", first_time

Q_index_first_occ = Q_index[bin_first_occ]
Q_index_first_occ = Q_index_first_occ.astype(int)
len_time_series = len(time_series)

# Max diversity of area AB
offset_dis_div1 = 0.
offset_dis_div2 = 0.

do_DivdD = args.DivdD
do_DivdE = args.DivdE
if do_DivdD:
	data_temp3 = 0.+data_temp
	data_temp3[data_temp3==1]=0
	data_temp3[data_temp3==2]=0
	data_temp3[data_temp3==3]=1
	div_traj_3 = np.nansum(data_temp3,axis=0)[0:-1]
	max_div_traj_3 = np.max(div_traj_3)
	offset_dis_div1 = max_div_traj_3
	offset_dis_div2 = max_div_traj_3
	if equal_d and do_symCovD == False:
		offset_dis_div1 = 0.
		offset_dis_div2 = 0.

# Median of diversity
offset_ext_div1 = 0.
offset_ext_div2 = 0.
if do_DivdE:
	offset_ext_div1 = np.median(div_traj_1)
	offset_ext_div2 = np.median(div_traj_2)
	if equal_e and do_symCovE:
		offset_ext_div = np.median( np.concatenate((div_traj_1, div_traj_2)) )
		offset_ext_div1 = offset_ext_div
		offset_ext_div2 = offset_ext_div
	if equal_e and do_args.symCovE == False:
		offset_ext_div1 = 0.
		offset_ext_div2 = 0.


# TODO: multiple traits and categories, multiple covar => complete refactoring needed!
if plot_file != "":
	if ("marginal_rates" in plot_file) == False or ("diversity" in plot_file) == False or ("dispersal" in plot_file) == False:
		if burnin==0: 
			print("""Burnin was set to 0. Use command -b to specify a higher burnin (e.g. -b 100 will exclude the first 100 samples).""")
		
		def get_covar_effect(covar, par, de, transf):
			len_par = len(par)
			len_covar = len(covar)
			rate = np.zeros((len_par, len_covar))
			for i in range(len_par):
				if transf == 1:
					rate[i,:] = de[i] * np.exp(par[i] * covar)
				if transf == 2: # DivdD
					tmp = de[i] * (1. - (covar/par[i]))
					tmp[tmp <= 0] = 0.
					rate[i:,] = tmp
				if transf == 3: # DivdE
					tmp = de[i] / (1. - (covar/par[i]))
					tmp[np.isfinite(tmp) == False] =  0.
					tmp[tmp <= 0] =  0.
					rate[i:,] = tmp
				if transf == 4: # DdE
					rate[i:,] = de[i] + par[i] * covar
				if transf == 5: # Trait dependence
					rate[i,:] = np.exp(np.log(de) + par * covar)
			hpd = np.zeros((2, len_covar))
			if len_par > 1:
				rate_mean = np.mean(rate, axis = 0)
				for i in range(len_covar):
					hpd[:,i] = calcHPD(rate[:,i], .95)
			else:
				rate_mean = rate[0,:]
				hpd[:] = np.NaN
			return rate_mean, hpd
		
		def get_covar_x1_trait_effect(covar, covarpar, trait, traitpar, de, transf):
			len_par = len(covarpar)
			len_covar = len(covar)
			len_trait = len(trait)
			rate = np.zeros((len_covar, len_trait, len_par))
			for i in range(len_par):
				for y in range(len_trait):
					if transf == 1:
						rate_tmp = de[i] * np.exp(covarpar[i] * covar)
					if transf == 2: # DivdD
						tmp = de[i] * (1. - (covar/covarpar[i]))
						tmp[tmp <= 0] = 0.
						rate_tmp = tmp
					if transf == 3: # DivdE
						tmp = de[i] / (1. - (covar/covarpar[i]))
						tmp[tmp <= 0] = np.NaN
						tmp[np.isfinite(tmp) == False] = 0.
						tmp[tmp <= 0] = 0.
						rate_tmp = tmp
					if transf == 4: # DdE
						rate_tmp = de[i] + covarpar[i] * covar
					rate[:,y,i] = np.exp(np.log(rate_tmp) + traitpar[i] * trait[y])
			if len_par > 1:
				rate_mean = np.mean(rate, axis = 2)
			else:
				rate_mean = rate[:,:,0]
			return rate_mean
		
		head = next(open(plot_file)).split()
		logfile = loadtxt(plot_file, skiprows=max(1,burnin))
		mcmc_logfile = logfile.ndim == 2
		e1_index = [head.index(i) for i in head if "e1" in i]
		e1_index = min(e1_index)
		e2_index = [head.index(i) for i in head if "e2" in i]
		e2_index = min(e2_index)
		cov_d12_index = head.index("cov_d12")
		cov_d21_index = head.index("cov_d21")
		cov_e1_index = head.index("cov_e1")
		cov_e2_index = head.index("cov_e2")
		a_d_index = head.index("a_d")
		a_e_index = head.index("a_e")
		panel_count = 0
		if mcmc_logfile:
			d12 = logfile[:,4]
			d21 = logfile[:,5]
			e1 = logfile[:,e1_index]
			e2 = logfile[:,e2_index]
			cov_d12 = logfile[:,cov_d12_index]
			cov_d21 = logfile[:,cov_d21_index]
			cov_e1 = logfile[:,cov_e1_index]
			cov_e2 = logfile[:,cov_e2_index]
			a_d = logfile[:,a_d_index]
			a_e = logfile[:,a_e_index]
		else:
			d12 = np.array([logfile[4]])
			d21 = np.array([logfile[5]])
			e1 = np.array([logfile[e1_index]])
			e2 = np.array([logfile[e2_index]])
			cov_d12 = np.array([logfile[cov_d12_index]])
			cov_d21 = np.array([logfile[cov_d21_index]])
			cov_e1 = np.array([logfile[cov_e1_index]])
			cov_e2 = np.array([logfile[cov_e2_index]])
			a_d = np.array([logfile[a_d_index]])
			a_e = np.array([logfile[a_e_index]])
		
		plot_dis = 0
		plot_ext = 0
		covar_x_trait = 0
		if args.varD != "" and argstraitD == "":
			panel_count += 2
			plot_dis = 1
			covarD = np.linspace(np.min(time_varD), np.max(time_varD), 100)
			d12_mean, d12_hpd = get_covar_effect(covarD, cov_d12, d12, 1)
			d21_mean, d21_hpd = get_covar_effect(covarD, cov_d21, d21, 1)
			if rescale_factor > 0:
				covarD = covarD + mean_varD_before_centering[0]
				covarD = covarD / rescale_factor
			else:
				covarD = covarD * (time_varD_unscmax - time_varD_unscmin) + time_varD_unscmean
		elif args.DivdD and argstraitD == "":
			panel_count += 2
			plot_dis = 1
			covarD = np.linspace(1., np.min((np.max(cov_d12), np.max(cov_d21))), 100)
			d12_mean, d12_hpd = get_covar_effect(covarD, cov_d12, d12, 2)
			d21_mean, d21_hpd = get_covar_effect(covarD, cov_d21, d21, 2)
		elif argstraitD != "" and args.varD == "" and args.DivdD is False:
			panel_count += 2
			plot_dis = 1
			covarD = np.linspace(np.min(traitD_untrans), np.max(traitD_untrans), 100)
			traitD_eff = np.log(covarD) - np.mean(np.log(traitD_untrans))
			d12_mean, d12_hpd = get_covar_effect(traitD_eff, a_d, d12, 5)
			d21_mean, d21_hpd = get_covar_effect(traitD_eff, a_d, d21, 5)
		else:
			covar_x_trait = 1
		if args.varE != "" and argstraitE == "":
			panel_count += 2
			plot_ext = 1
			covarE = np.linspace(np.min(time_varE), np.max(time_varE), 100)
			e1_mean, e1_hpd = get_covar_effect(covarE, cov_e1, e1, 1)
			e2_mean, e2_hpd = get_covar_effect(covarE, cov_e2, e2, 1)
			if rescale_factor > 0:
				covarE = covarE + mean_varE_before_centering[0]
				covarE = covarE / rescale_factor
			else:
				covarE = covarE * (time_varE_unscmax - time_varE_unscmin) + time_varE_unscmean
		elif args.DivdE and argstraitE == "":
			panel_count += 2
			plot_ext = 1
			covarE = np.linspace(1., np.min((np.max(cov_e1), np.max(cov_e2))), 100)
			e1_mean, e1_hpd = get_covar_effect(covarE, cov_e1, e1, 3)
			e2_mean, e2_hpd = get_covar_effect(covarE, cov_e2, e2, 3)
		elif args.DdE and argstraitE == "":
			panel_count += 2
			plot_ext = 1
			covarE = np.linspace(0., 0.5, 100)
			e1_mean, e1_hpd = get_covar_effect(covarE, cov_e1, e1, 4)
			e2_mean, e2_hpd = get_covar_effect(covarE, cov_e2, e2, 4)
		elif argstraitE != "" and args.varE == "" and args.DivdE is False and args.DdE is False:
			panel_count += 2
			plot_ext = 1
			covarE = np.linspace(np.min(traitE_untrans), np.max(traitE_untrans), 100)
			traitE_eff = np.log(covarE) - np.mean(np.log(traitE_untrans))
			e1_mean, e1_hpd = get_covar_effect(traitE_eff, a_e, e1, 5)
			e2_mean, e2_hpd = get_covar_effect(traitE_eff, a_e, e2, 5)
		else:
			covar_x_trait = 1

		if covar_x_trait == 1: # covariate x trait interaction
			covar_x_trait = 1
			covarD = np.zeros(100)
			covarE = np.zeros(100)
			covarD_eff = np.zeros(100)
			covarE_eff = np.zeros(100)
			traitD_plot = np.ones(100)
			traitE_plot = np.ones(100)
			traitD_eff = np.zeros(100)
			traitE_eff = np.zeros(100)
			transfD = 1
			transfE = 1
			panel_count = 4
			plot_dis = 1
			plot_ext = 1
			if argstraitD != "":
				traitD_plot = np.linspace(np.min(traitD_untrans), np.max(traitD_untrans), 100)
				traitD_eff = np.log(traitD_plot) - np.mean(np.log(traitD_untrans))
			if argstraitE != "":
				traitE_plot = np.linspace(np.min(traitE_untrans), np.max(traitE_untrans), 100)
				traitE_eff = np.log(traitE_plot) - np.mean(np.log(traitE_untrans))
			if args.varD != "":
				transfD = 1
				covarD_eff = np.linspace(np.min(time_varD), np.max(time_varD), 100)
				if rescale_factor > 0:
					covarD = covarE_eff + mean_varD_before_centering[0]
					covarD = covarD / rescale_factor
				else:
					covarD = covarD_eff * (time_varD_unscmax - time_varD_unscmin) + time_varD_unscmean
			if args.DivdD:
				transfD = 2
				plot_dis = 1
				covarD = np.linspace(1., np.min((np.max(cov_d12), np.max(cov_d21))), 100)
				covarD_eff = covarD
			if args.varE != "":
				transfE = 1
				covarE_eff = np.linspace(np.min(time_varE), np.max(time_varE), 100)
				if rescale_factor > 0:
					covarE = covarE_eff + mean_varE_before_centering[0]
					covarE = covarE / rescale_factor
				else:
					covarE = covarE_eff * (time_varE_unscmax - time_varE_unscmin) + time_varE_unscmean
			if args.DivdE:
				transfE = 3
				plot_ext = 1
				covarE = np.linspace(1., np.min((np.max(cov_e1), np.max(cov_e2))), 100)
				covarE_eff = covarE
			if args.DdE:
				transfE = 4
				plot_ext = 1
				covarE = np.linspace(0., 0.5, 100)
				covarE_eff = covarE
			d12_mean = get_covar_x_trait_effect(covarD_eff, cov_d12, traitD_eff, a_d, d12, transfD)
			d21_mean = get_covar_x_trait_effect(covarD_eff, cov_d21, traitD_eff, a_d, d21, transfD)
			e1_mean = get_covar_x_trait_effect(covarE_eff, cov_e1, traitE_eff, a_e, e1, transfE)
			e2_mean = get_covar_x_trait_effect(covarE_eff, cov_e2, traitE_eff, a_e, e2, transfE)
		
		
		# write R file
		print("\ngenerating R file...", end=' ')
		output_wd = os.path.dirname(plot_file)
		name_file = os.path.splitext(os.path.basename(plot_file))[0]
		out = "%s/%s_Covar_effect.r" % (output_wd, name_file)
		newfile = open(out, "w")
		r_script = print_R_vec('\npanel_count', np.array([panel_count]))
		if platform.system() == "Windows" or platform.system() == "Microsoft":
			wd_forward = os.path.abspath(output_wd).replace('\\', '/')
			r_script += "\npdf(file='%s/%s_Covar_effect.pdf', width = 0.6*10, height = 0.6*2.5*panel_count, pointsize = 8, useDingbats = FALSE)\n" % (wd_forward, name_file)
		else:
			r_script += "\npdf(file='%s/%s_Covar_effect.pdf', width = 0.6*10, height = 0.6*2.5*panel_count, pointsize = 8, useDingbats = FALSE)\n" % (output_wd, name_file)

		if plot_dis == 1 and covar_x_trait == 0:
			r_script += "\nlayout(matrix(1:panel_count, ncol = 2, nrow = panel_count/2, byrow = TRUE))"
			r_script += "\npar(las = 1, mar = c(4, 4, 0.5, 0.5))"
			r_script += print_R_vec('\ntime_varD', covarD)
			r_script += print_R_vec('\nd12_mean', d12_mean)
			r_script += print_R_vec('\nd21_mean', d21_mean)
			r_script += print_R_vec('\nd12_lwr', d12_hpd[0,:])
			r_script += print_R_vec('\nd21_lwr', d21_hpd[0,:])
			r_script += print_R_vec('\nd12_upr', d12_hpd[1,:])
			r_script += print_R_vec('\nd21_upr', d21_hpd[1,:])
			r_script += "\nYlim_d = max(c(d12_mean, d21_mean, d12_upr, d21_upr), na.rm = TRUE)"
			r_script += "\nplot(time_varD, d12_mean, type = 'n', ylim = c(0, Ylim_d), xlab = 'Covariate dispersal', ylab = 'd12')"
			r_script += "\npolygon(c(time_varD, rev(time_varD)), c(d12_lwr, rev(d12_upr)), col = adjustcolor('#4c4cec', alpha = 0.3), border = NA)"
			r_script += "\nlines(time_varD, d12_mean, col = '#4c4cec', lwd = 2)"
			r_script += "\nplot(time_varD, d21_mean, type = 'n', ylim = c(0, Ylim_d), xlab = 'Covariate dispersal', ylab = 'd21')"
			r_script += "\npolygon(c(time_varD, rev(time_varD)), c(d21_lwr, rev(d21_upr)), col = adjustcolor('#4c4cec', alpha = 0.3), border = NA)"
			r_script += "\nlines(time_varD, d21_mean, col = '#4c4cec', lwd = 2)"
		if plot_ext == 1 and covar_x_trait == 0:
			if plot_dis != 1:
				r_script += "\nlayout(matrix(1:panel_count, ncol = 2, nrow = panel_count/2, byrow = TRUE))"
				r_script += "\npar(las = 1, mar = c(4, 4, 0.5, 0.5))"
			r_script += print_R_vec('\ntime_varE', covarE)
			r_script += print_R_vec('\ne1_mean', e1_mean)
			r_script += print_R_vec('\ne2_mean', e2_mean)
			r_script += print_R_vec('\ne1_lwr', e1_hpd[0,:])
			r_script += print_R_vec('\ne2_lwr', e2_hpd[0,:])
			r_script += print_R_vec('\ne1_upr', e1_hpd[1,:])
			r_script += print_R_vec('\ne2_upr', e2_hpd[1,:])
			r_script += "\nYlim_e = max(c(e1_mean, e2_mean, e1_upr, e2_upr), na.rm = TRUE)"
			r_script += "\nplot(time_varE, e1_mean, type = 'n', ylim = c(0, Ylim_e), xlab = 'Covariate extinction', ylab = 'e1')"
			r_script += "\npolygon(c(time_varE, rev(time_varE)), c(e1_lwr, rev(e1_upr)), col = adjustcolor('#e34a33', alpha = 0.3), border = NA)"
			r_script += "\nlines(time_varE, e1_mean, col = '#e34a33', lwd = 2)"
			r_script += "\nplot(time_varE, e2_mean, type = 'n', ylim = c(0, Ylim_e), xlab = 'Covariate extinction', ylab = 'e2')"
			r_script += "\npolygon(c(time_varE, rev(time_varE)), c(e2_lwr, rev(e2_upr)), col = adjustcolor('#e34a33', alpha = 0.3), border = NA)"
			r_script += "\nlines(time_varE, e2_mean, col = '#e34a33', lwd = 2)"
		if covar_x_trait == 1:
			r_script += "\nlayout(matrix(1:8, ncol = 4, nrow = 2, byrow = TRUE), widths = c(0.4, 0.1, 0.4, 0.1))"
			r_script += "\nget_axis_ticks <- function(v) {"
			r_script += "\n  res <- data.frame(at = 50, labels = '')"
			r_script += "\n  if (var(v) != 0) {"
			r_script += "\n    ticks <- axisTicks(range(v), log = FALSE)"
			r_script += "\n    coef_lm <- lm(c(1:100) ~ v)$coef"
			r_script += "\n    at <- coef_lm[1] + ticks * coef_lm[2]"
			r_script += "\n    res <- data.frame(at = at, labels = ticks)"
			r_script += "\n  }"
			r_script += "\n  return(res)"
			r_script += "\n}"
			r_script += print_R_vec('\ncovarD', covarD)
			r_script += print_R_vec('\ntraitD', traitD_plot)
			r_script += print_R_vec('\ncovarE', covarE)
			r_script += print_R_vec('\ntraitE', traitE_plot)
			r_script += print_R_vec('\nd12_mean', d12_mean.flatten())
			r_script += print_R_vec('\nd21_mean', d21_mean.flatten())
			r_script += print_R_vec('\ne1_mean', e1_mean.flatten())
			r_script += print_R_vec('\ne2_mean', e2_mean.flatten())
			r_script += "\nd12_mean <- matrix(d12_mean, 100, 100, byrow = TRUE)"
			r_script += "\nd21_mean <- matrix(d21_mean, 100, 100, byrow = TRUE)"
			r_script += "\ne1_mean <- matrix(e1_mean, 100, 100, byrow = TRUE)"
			r_script += "\ne2_mean <- matrix(e2_mean, 100, 100, byrow = TRUE)"
			
			r_script += "\ncolpal <- colorRampPalette(c('white', '#4c4cec'))"
			r_script += "\nzlim_d <- c(min(c(d12_mean, d21_mean)), max(c(d12_mean, d21_mean)))"
			r_script += "\nscale_d <- seq(zlim_d[1], zlim_d[2], length.out = 100)"
			r_script += "\npar(las = 1, mar = c(4, 4, 0.5, 0.5))"
			r_script += "\nimage(y = 1:100, x = 1:100, z = d12_mean, zlim = zlim_d, xaxt = 'n', yaxt = 'n', xlab = 'Covariate', ylab = 'Trait', col = colpal(100))"
			r_script += "\nx_ticks <- get_axis_ticks(covarD)"
			r_script += "\ny_ticks <- get_axis_ticks(traitD)"
			r_script += "\naxis(side = 1, at = x_ticks[, 1], labels = x_ticks[, 2])"
			r_script += "\naxis(side = 2, at = y_ticks[, 1], labels = y_ticks[, 2])"
			r_script += "\nbox()"
			r_script += "\npar(las = 1, mar = c(5, 0.5, 4, 4))"
			r_script += "\nimage(1, scale_d, matrix(scale_d, ncol = 100), xaxt = 'n', yaxt = 'n', xlab = '', ylab = '', col = colpal(100), main = 'd12')"
			r_script += "\naxis(side = 4)"
			r_script += "\nbox()"
			r_script += "\npar(las = 1, mar = c(4, 4, 0.5, 0.5))"
			r_script += "\nimage(y = 1:100, x = 1:100, z = d21_mean, zlim = zlim_d, xaxt = 'n', yaxt = 'n', xlab = 'Covariate', ylab = 'Trait', col = colpal(100))"
			r_script += "\naxis(side = 1, at = x_ticks[, 1], labels = x_ticks[, 2])"
			r_script += "\naxis(side = 2, at = y_ticks[, 1], labels = y_ticks[, 2])"
			r_script += "\nbox()"
			r_script += "\npar(las = 1, mar = c(5, 0.5, 4, 4))"
			r_script += "\nimage(1, scale_d, matrix(scale_d, ncol = 100), xaxt = 'n', yaxt = 'n', xlab = '', ylab = '', col = colpal(100), main = 'd21')"
			r_script += "\naxis(side = 4)"
			r_script += "\nbox()"
			r_script += "\ncolpal <- colorRampPalette(c('white', '#e34a33'))"
			r_script += "\nzlim_e <- c(min(c(e1_mean, e2_mean)), max(c(e1_mean, e2_mean)))"
			r_script += "\nscale_e <- seq(zlim_e[1], zlim_e[2], length.out = 100)"
			r_script += "\npar(las = 1, mar = c(4, 4, 0.5, 0.5))"
			r_script += "\nimage(y = 1:100, x = 1:100, z = e1_mean, zlim = zlim_e, xaxt = 'n', yaxt = 'n', xlab = 'Covariate', ylab = 'Trait', col = colpal(100))"
			r_script += "\nx_ticks <- get_axis_ticks(covarE)"
			r_script += "\ny_ticks <- get_axis_ticks(traitE)"
			r_script += "\naxis(side = 1, at = x_ticks[, 1], labels = x_ticks[, 2])"
			r_script += "\naxis(side = 2, at = y_ticks[, 1], labels = y_ticks[, 2])"
			r_script += "\nbox()"
			r_script += "\npar(las = 1, mar = c(5, 0.5, 4, 4))"
			r_script += "\nimage(1, scale_e, matrix(scale_e, ncol = 100), xaxt = 'n', yaxt = 'n', xlab = '', ylab = '', col = colpal(100), main = 'e1')"
			r_script += "\naxis(side = 4)"
			r_script += "\nbox()"
			r_script += "\npar(las = 1, mar = c(4, 4, 0.5, 0.5))"
			r_script += "\nimage(y = 1:100, x = 1:100, z = e2_mean, zlim = zlim_e, xaxt = 'n', yaxt = 'n', xlab = 'Covariate', ylab = 'Trait', col = colpal(100))"
			r_script += "\naxis(side = 1, at = x_ticks[, 1], labels = x_ticks[, 2])"
			r_script += "\naxis(side = 2, at = y_ticks[, 1], labels = y_ticks[, 2])"
			r_script += "\nbox()"
			r_script += "\npar(las = 1, mar = c(5, 0.5, 4, 4))"
			r_script += "\nimage(1, scale_e, matrix(scale_e, ncol = 100), xaxt = 'n', yaxt = 'n', xlab = '', ylab = '', col = colpal(100), main = 'e2')"
			r_script += "\naxis(side = 4)"
			r_script += "\nbox()"
		r_script+="\ndev.off()"
		newfile.writelines(r_script)
		newfile.close()

		print("\nAn R script with the source for the RTT plot was saved as: %s_Covar_effect.r\n(in %s)" % (name_file, output_wd))
		if platform.system() == "Windows" or platform.system() == "Microsoft":
			cmd="cd %s & Rscript %s_%s_Covar_effect.r" % (output_wd, name_file, name_file)
		else:
			cmd="cd %s; Rscript %s/%s_Covar_effect.r" % (output_wd, output_wd, name_file)
		os.system(cmd)
		print("done\n")
	sys.exit("\n")

#### INIT LOG FILES
logfile = open(out_log , "w")
head="it\tposterior\tprior\tlikelihood"
Q_times_header = np.concatenate((0., Q_times), axis = None)[::-1]
for i in range(len(dis_rate_vec)): head+= "\td12_t%s\td21_t%s" % (Q_times_header[i],Q_times_header[i])
for i in range(len(ext_rate_vec)): head+= "\te1_t%s\te2_t%s" % (Q_times_header[i],Q_times_header[i])
for i in range(n_Q_times): head+= "\tq1_t%s\tq2_t%s" % (Q_times_header[i],Q_times_header[i])
if do_varD: 
	for i in range(num_varD):
		head += "\tcov%s_d12\tcov%s_d21" % (i + 1, i + 1)
	if args.lgD:
		for i in range(num_varD):
			head += "\tx0%s_d12\tx0%s_d21" % (i + 1, i + 1)
if do_DivdD: head += "\tK_d12\tK_d21"
if do_varE:
	for i in range(num_varE):
		head += "\tcov%s_e1\tcov%s_e2" % (i + 1, i + 1)
	if args.lgE:
		for i in range(num_varE):
			head += "\tx0%s_e1\tx0%s_e2" % (i + 1, i + 1)
if do_DivdE: head += "\tK_e1\tK_e2"
if argsDdE: head += "\tphi_e1\tphi_e2"
if argsG: head+= "\talpha"
if do_DivdD or do_DivdE:
	slices_dis = dis_rate_vec.shape[0]
	slices_ext = ext_rate_vec.shape[0]
	max_slices = max(slices_dis, slices_ext)
	if data_in_area == 0:
		for i in range(max_slices): head+= "\tcarrying_capacity_1_t%s\tcarrying_capacity_2_t%s" % (i,i)
	else:
		for i in range(max_slices): head+= "\tcarrying_capacity_t%s" % (i)
#head+="\ta_d\ta_e"
for i in range(num_traitD): head+= "\tk%s_d" % (i + 1)
for i in range(num_traitE): head+= "\tk%s_e" % (i + 1)
if any(num_catD > 0):
	for i in range(len(num_catD)):
		catD_y = np.unique(catD[:,i]).astype(int)
		catD_y = catD_y - np.min(catD_y)
		for y in catD_y:
			head += "\tcat%s_%s_d" % (i + 1, y + 1)
	head += "\thp_cat_d"
if any(num_catE > 0):
	for i in range(len(num_catE)):
		catE_y = np.unique(catE[:,i]).astype(int)
		catE_y = catE_y - np.min(catE_y)
		for y in catE_y:
			head += "\tcat%s_%s_e" % (i + 1, y + 1)
	head += "\thp_cat_e"
head+="\thp_rate\tbeta"


head=head.split("\t")
wlog=csv.writer(logfile, delimiter='\t')
wlog.writerow(head)

ratesfile = open(out_rates , "w") 
head="it"
ts_rev = time_series[1:][::-1]
for i in range(len(time_varD)): head+= "\td12_%s" % (ts_rev[i])
for i in range(len(time_varD)): head+= "\td21_%s" % (ts_rev[i])
for i in range(len(time_varE)): head+= "\te1_%s" % (ts_rev[i])
for i in range(len(time_varE)): head+= "\te2_%s" % (ts_rev[i])
head=head.split("\t")
rlog=csv.writer(ratesfile, delimiter='\t')
rlog.writerow(head)

if args.log_div:
	out_div ="%s/%s_%s%s%s%s%s_diversity.log" % (output_wd,name_file,simulation_no,Q_times_str,ti_tag,model_tag,args.out)
	divfile = open(out_div, "w")
	head="it"
	for i in range(len(ts_rev)): head+= "\tdiv1_%s" % (ts_rev[i])
	for i in range(len(ts_rev)): head+= "\tdiv2_%s" % (ts_rev[i])
	head=head.split("\t")
	divlog=csv.writer(divfile, delimiter='\t')
	divlog.writerow(head)
if args.log_dis:
	out_dis ="%s/%s_%s%s%s%s%s_dispersal.log" % (output_wd,name_file,simulation_no,Q_times_str,ti_tag,model_tag,args.out)
	disfile = open(out_dis, "w")
	head="it"
	for i in range(len(ts_rev)): head+= "\tdis12_%s" % (ts_rev[i])
	for i in range(len(ts_rev)): head+= "\tdis21_%s" % (ts_rev[i])
	head=head.split("\t")
	dislog=csv.writer(disfile, delimiter='\t')
	dislog.writerow(head)

# Use an ode solver to approximate the diversity trajectories
def div_dt(div, t, d12, d21, mu1, mu2, k_d1, k_d2, k_e1, k_e2):
	div1 = div[0]
	div2 = div[1]
	div3 = div[2]
	lim_d1 = max(0, 1 - (div1 + div3)/k_d1) # Limit dispersal into area 1
	lim_d2 = max(0, 1 - (div2 + div3)/k_d2) # Limit dispersal into area 2
	lim_e1 = max(1e-05, 1 - (div1 + div3)/k_e1) # Increases extinction in area 1
	lim_e2 = max(1e-05, 1 - (div2 + div3)/k_e2) # Increases extinction in area 2
	dS = np.zeros(5)
	dS[3] = d21 * div2 * lim_d1 # Gain area 1
	dS[4] = d12 * div1 * lim_d2 # Gain area 2
	mu1 = mu1/lim_e1
	mu2 = mu2/lim_e2
	dS[0] = -mu1 * div1 + mu2 * div3 - dS[4]
	dS[1] = -mu2 * div2 + mu1 * div3 - dS[3]
	dS[2] = -(mu1 + mu2) * div3 + dS[3] + dS[4]
	return dS


def div_traitcat_dt(div, t, d12, d21, mu1, mu2, k_d1, k_d2, k_e1, k_e2, covar_mu1, covar_mu2,
			trait_parD, traitD, trait_parE, traitE,
			cat_parD, catD, cat_parE, catE,
			argsDdE, argstraitD, argstraitE, argscatD, argscatE,
			pres1_idx, pres2_idx, pres3_idx, gainA_idx, gainB_idx, nTaxa):
	div1 = div[pres1_idx]
	div2 = div[pres2_idx]
	div3 = div[pres3_idx]
	div13 = sum(div1) + sum(div3)
	div23 = sum(div1) + sum(div3)
	lim_d1 = max(0, 1 - div13/k_d1) # Limit dispersal into area 1
	lim_d2 = max(0, 1 - div23/k_d2) # Limit dispersal into area 2
	dS = np.zeros(5 * nTaxa)
	if argstraitD: # Cont trait dis
		cont_modi = np.exp(np.sum(trait_parD * traitD, axis = 1))
		d12 = d12 * cont_modi
		d21 = d21 * cont_modi
	if argscatD: # Cat trait dis
		d12 = d12 * np.sum(cat_parD[catD], axis = 1)
		d21 = d21 * np.sum(cat_parD[catD], axis = 1)
	dS[gainA_idx] = d21 * div[pres2_idx] * lim_d1 # Gain area 1
	dS[gainB_idx] = d12 * div[pres1_idx] * lim_d2 # Gain area 2
	if argstraitE: # Cont trait
		cont_modi = np.exp(np.sum(trait_parE * traitE, axis = 1))
		mu1 = mu1 * cont_modi
		mu2 = mu2 * cont_modi
	if argscatE: # Cat trait
		mu1 = mu1 * np.sum(cat_parE[catE], axis = 1)
		mu2 = mu2 * np.sum(cat_parE[catE], axis = 1)
	if argsDdE: # Dispersal induced extinction
		mu1 = mu1 + covar_mu1 * dS[gainA_idx] / (div13 + 1.)
		mu2 = mu2 + covar_mu2 * dS[gainB_idx] / (div23 + 1.)
#	else:
	lim_e1 = max(1e-05, 1 - div13/k_e1) # Increases extinction in area 1
	lim_e2 = max(1e-05, 1 - div23/k_e2) # Increases extinction in area 2
	mu1 = mu1 / lim_e1
	mu2 = mu2 / lim_e2
	dS[pres1_idx] = -mu1 * div[pres1_idx] + mu2 * div[pres3_idx] - dS[gainB_idx]
	dS[pres2_idx] = -mu2 * div[pres2_idx] + mu1 * div[pres3_idx] - dS[gainA_idx]
	dS[pres3_idx] = -(mu1 + mu2) * div[pres3_idx] + dS[gainA_idx] + dS[gainB_idx]
	return dS

def dis_dep_ext_dt(div, t, d12, d21, mu1, mu2, k_d1, k_d2, covar_mu1, covar_mu2):
	div1 = div[0]
	div2 = div[1]
	div3 = div[2]
	div13 = div[0] + div[2]
	div23 = div[1] + div[2]
	lim_d1 = max(0, 1 - (div13)/k_d1) # Limit dispersal into area 1
	lim_d2 = max(0, 1 - (div23)/k_d2) # Limit dispersal into area 2
	dS = np.zeros(5)
	dS[3] = d21 * div2 * lim_d1 # Gain area 1
	dS[4] = d12 * div1 * lim_d2 # Gain area 2
	mu1 = mu1 + covar_mu1 * dS[3] / (div13 + 1.)
	mu2 = mu2 + covar_mu2 * dS[4] / (div23 + 1.)
	dS[0] = -mu1 * div1 + mu2 * div3 - dS[4]
	dS[1] = -mu2 * div2 + mu1 * div3 - dS[3]
	dS[2] = -(mu1 + mu2) * div3 + dS[3] + dS[4]
	return dS

#div_int = odeint(div_dep_ext_dt, np.array([1., 1., 0., 0., 0.]), [0, 1], args = (0.2, 0.2, 0.1, 0.1, np.inf, np.inf, 0.2, 0.2))
#div_int

def approx_div_traj(nTaxa, dis_rate_vec, ext_rate_vec, 
			do_DivdD, do_DivdE, do_varD, do_varE, argsDdE, argsG,
			r_vec, alpha, YangGammaQuant, pp_gamma_ncat, bin_size, Q_index, Q_index_first_occ,
			covar_par, covar_parD, covar_parE, offset_dis_div1, offset_dis_div2, offset_ext_div1, offset_ext_div2,
			time_series, len_time_series, bin_first_occ, first_area, time_varD, time_varE, data_temp,
			trait_parD, traitD, trait_parE, traitE,
			cat_parD, catD, cat_parE, catE, argstraitD, argstraitE, argscatD, argscatE):
	if argsG:
		YangGamma = get_gamma_rates(alpha, YangGammaQuant, pp_gamma_ncat)
		sa = np.zeros((pp_gamma_ncat, nTaxa))
		sb = np.zeros((pp_gamma_ncat, nTaxa))
		for i in range(pp_gamma_ncat):
			sa[i,:] = exp(-bin_size * YangGamma[i] * -log(r_vec[Q_index_first_occ, 1])/bin_size)
			sb[i,:] = exp(-bin_size * YangGamma[i] * -log(r_vec[Q_index_first_occ, 2])/bin_size)
		sa = sa * weight_per_taxon.T
		sb = sb * weight_per_taxon.T
		sa = np.nansum(sa, axis = 0)
		sb = np.nansum(sb, axis = 0)
	else:	
		sa = r_vec[Q_index_first_occ, 1]
		sb = r_vec[Q_index_first_occ, 2]
	sa[first_area == 1.] = 0. # No false absence if taxon is observed in 1
	sb[first_area == 2.] = 0. # No false absence if taxon is observed in 2
	sa[first_area == 3.] = 0. # No false absence if taxon is observed in 3
	sb[first_area == 3.] = 0. # No false absence if taxon is observed in 3
	# Add artificial bin before start of the time series
	# padded_time = time_series[0] + time_series[0] - time_series[1]
	time_series_pad = time_series#np.concatenate((padded_time, time_series[0:-1]), axis = None)
	time_varD_pad = time_varD#np.concatenate((time_varD[0], time_varD[0:-1]), axis = None)
	time_varE_pad = time_varE#np.concatenate((time_varE[0], time_varD[0:-1]), axis = None)
	idx_covar_parD1 = np.arange(0, len(covar_parD), 2, dtype = int)
	idx_covar_parD2 = np.arange(1, len(covar_parD), 2, dtype = int)
	idx_covar_parE1 = np.arange(0, len(covar_parE), 2, dtype = int)
	idx_covar_parE2 = np.arange(1, len(covar_parE), 2, dtype = int)
	if traits is False and cat is False:
		div_1 = np.zeros(len_time_series)
		div_2 = np.zeros(len_time_series)
		div_3 = np.zeros(len_time_series)
		gain_1 = np.zeros(len_time_series)
		gain_2 = np.zeros(len_time_series)
		pres = np.ones((len_time_series, 3 * nTaxa))
		for i in range(1, len_time_series):
			k_d1 = np.inf
			k_d2 = np.inf
			if do_DivdD:
				dis_rate_vec_i = dis_rate_vec[0,:]
				k_d1 = covar_par[0]
				k_d2 = covar_par[1]
				dis_rate_vec_i = dis_rate_vec_i / (1.- [offset_dis_div2, offset_dis_div1]/covar_par[0:2])
			elif do_varD:
				dis_rate_vec_i = dis_rate_vec[0,:]
				dis_rate_vec_i = np.array([dis_rate_vec_i[0] * np.exp(np.sum(covar_parD[idx_covar_parD1] * time_varD[i - 1, :])), dis_rate_vec_i[1] * np.exp(np.sum(covar_parD[idx_covar_parD1] * time_varD[i - 1, :]))])
			else:
				dis_rate_vec_i = dis_rate_vec[i - 1, ]

			k_e1 = np.inf
			k_e2 = np.inf
			if do_DivdE:
				ext_rate_vec_i = ext_rate_vec[0,:]
				if data_in_area != 0:
					covar_par[[4 - data_in_area]] = 1e5
				k_e1 = covar_par[2]
				k_e2 = covar_par[3]
				ext_rate_vec_i = ext_rate_vec_i * (1 - ([offset_ext_div1, offset_ext_div2]/covar_par[2:4]))
				ext_rate_vec_i[np.isfinite(ext_rate_vec_i) == False] = 1e-5 # nan for data_in_area
			elif do_varE:
				ext_rate_vec_i = ext_rate_vec[0,:]
				ext_rate_vec_i = np.array([ext_rate_vec_i[0] * np.exp(np.sum(covar_parE[idx_covar_parE1] * time_varE[i - 1, :])), ext_rate_vec_i[1] * np.exp(np.sum(covar_parE[idx_covar_parE1] * time_varE[i - 1, :]))])
			elif argsDdE:
				ext_rate_vec_i = ext_rate_vec[0,:]
				covar_mu1 = covar_par[2]
				covar_mu2 = covar_par[3]
			else:
				ext_rate_vec_i = ext_rate_vec[i - 1,:]

			d12 = dis_rate_vec_i[0]
			d21 = dis_rate_vec_i[1]
			mu1 = ext_rate_vec_i[0]
			mu2 = ext_rate_vec_i[1]

			occ_i = bin_first_occ == i # Only taxa occuring at that time for the first time
			sa_i = sa[occ_i]
			sb_i = sb[occ_i]
			sum_sa_i = sum(sa_i) # Summed probability of false absences in area 1
			sum_sb_i = sum(sb_i)
			first_area_i = first_area[occ_i]
			new_1 = sum(first_area_i == 1.) - sum_sb_i # Observed area 1 - false absences in area 1 (which are then in 3)
			new_2 = sum(first_area_i == 2.) - sum_sa_i
			new_3 = sum(first_area_i == 3.) + sum_sa_i + sum_sb_i

			dt = [0., time_series_pad[i - 1] - time_series_pad[i] ]
			div_t = np.zeros(5)
			div_t[0] = div_1[i - 1]
			div_t[1] = div_2[i - 1]
			div_t[2] = div_3[i - 1]

			if argsDdE:
				div_int = odeint(dis_dep_ext_dt, div_t, dt, args = (d12, d21, mu1, mu2, k_d1, k_d2, covar_mu1, covar_mu2), mxstep = 100)
			else:
				div_int = odeint(div_dt, div_t, dt, args = (d12, d21, mu1, mu2, k_d1, k_d2, k_e1, k_e2))

			div_1[i] = div_int[1,0] + new_1
			div_2[i] = div_int[1,1] + new_2
			div_3[i] = div_int[1,2] + new_3
			gain_1[i] = div_int[1,3]
			gain_2[i] = div_int[1,4]
	else: # Traits and categorical
		pres = np.zeros((len_time_series, 5 * nTaxa)) # time x probability of taxa presence - all presences could be case for a 3D array
		pres1_idx = np.arange(0, 5 * nTaxa, 5)
		pres2_idx = pres1_idx + 1
		pres3_idx = pres1_idx + 2
		gainA_idx = pres1_idx + 3
		gainB_idx = pres1_idx + 4
		for i in range(1, len_time_series):
			k_d1 = np.inf
			k_d2 = np.inf
			if do_DivdD:
				dis_rate_vec_i = dis_rate_vec[0,:]
				k_d1 = covar_par[0]
				k_d2 = covar_par[1]
				dis_rate_vec_i = dis_rate_vec_i / (1.- [offset_dis_div2, offset_dis_div1]/covar_par[0:2])
			elif do_varD:
				dis_rate_vec_i = dis_rate_vec[0,:]
				dis_rate_vec_i = np.array([dis_rate_vec_i[0] * np.exp(np.sum(covar_parD[idx_covar_parD1] * time_varD[i - 1, :])), dis_rate_vec_i[1] * np.exp(np.sum(covar_parD[idx_covar_parD1] * time_varD[i - 1, :]))])
			else:
				dis_rate_vec_i = dis_rate_vec[i - 1,:]

			k_e1 = np.inf
			k_e2 = np.inf
			covar_mu1 = 0.
			covar_mu2 = 0.
			if do_DivdE:
				ext_rate_vec_i = ext_rate_vec[0,:]
				if data_in_area != 0:
					covar_par[[4 - data_in_area]] = 1e5
				k_e1 = covar_par[2]
				k_e2 = covar_par[3]
				ext_rate_vec_i = ext_rate_vec_i * (1 - ([offset_ext_div1, offset_ext_div2]/covar_par[2:4]))
				ext_rate_vec_i[np.isfinite(ext_rate_vec_i) == False] = 1e-5 # nan for data_in_area
			elif do_varE:
				ext_rate_vec_i = ext_rate_vec[0,:]
				ext_rate_vec_i = np.array([ext_rate_vec_i[0] * np.exp(np.sum(covar_parE[idx_covar_parE1] * time_varE[i - 1, :])), ext_rate_vec_i[1] * np.exp(np.sum(covar_parE[idx_covar_parE1] * time_varE[i - 1, :]))])
			elif argsDdE:
				ext_rate_vec_i = ext_rate_vec[0,:]
				covar_mu1 = covar_par[2]
				covar_mu2 = covar_par[3]
			else:
				ext_rate_vec_i = ext_rate_vec[i - 1, ]

			d12 = dis_rate_vec_i[0]
			d21 = dis_rate_vec_i[1]
			mu1 = ext_rate_vec_i[0]
			mu2 = ext_rate_vec_i[1]
			# Preservation stuff
			occ_i = bin_first_occ == i # Only taxa occuring at that time for the first time
			new_1 = np.zeros(nTaxa)
			new_2 = np.zeros(nTaxa)
			new_3 = np.zeros(nTaxa)
			if any(occ_i):
				occ_area_1 = np.logical_and(occ_i, first_area == 1.)
				occ_area_2 = np.logical_and(occ_i, first_area == 2.)
				occ_area_3 = np.logical_and(occ_i, first_area == 3.)
				false_absence_area_2 = sb * occ_area_1
				false_absence_area_1 = sa * occ_area_2
				new_1 = occ_area_1 - false_absence_area_2
				new_2 = occ_area_2 - false_absence_area_1
				new_3 = occ_area_3 + false_absence_area_1 + false_absence_area_2
			
			dt = [0., time_series_pad[i - 1] - time_series_pad[i] ]
			div_t = pres[i - 1,:]
			
			div_int = odeint(div_traitcat_dt, div_t, dt, args = (d12, d21, mu1, mu2, k_d1, k_d2, k_e1, k_e2, covar_mu1, covar_mu2,
										trait_parD, traitD, trait_parE, traitE,
										cat_parD, catD, cat_parE, catE,
										argsDdE, argstraitD, argstraitE, argscatD, argscatE,
										pres1_idx, pres2_idx, pres3_idx, gainA_idx, gainB_idx, nTaxa), mxstep = 100)
			
			pres[i, pres1_idx] = div_int[1, pres1_idx] + new_1
			pres[i, pres2_idx] = div_int[1, pres2_idx] + new_2
			pres[i, pres3_idx] = div_int[1, pres3_idx] + new_3
			pres[i, gainA_idx] = div_int[1, gainA_idx]
			pres[i, gainB_idx] = div_int[1, gainB_idx]
		div_1 = np.sum(pres[:, pres1_idx], axis = 1) # rowsums are axis 1!
		div_2 = np.sum(pres[:, pres2_idx], axis = 1)
		div_3 = np.sum(pres[:, pres3_idx], axis = 1)
		gain_1 = np.sum(pres[:, gainA_idx], axis = 1)
		gain_2 = np.sum(pres[:, gainB_idx], axis = 1)
		not_extinct = np.isin(data_temp[:,-1], 0) != True
		pres[-1, pres1_idx[not_extinct]] = 0
		pres[-1, pres2_idx[not_extinct]] = 0
		pres[-1, pres3_idx[not_extinct]] = 0
		pres[-1, pres1_idx[np.isin(data_temp[:,-1], 1)]] = 1
		pres[-1, pres2_idx[np.isin(data_temp[:,-1], 2)]] = 1
		pres[-1, pres3_idx[np.isin(data_temp[:,-1], 3)]] = 1
		pres = pres[:, np.sort(np.concatenate((pres1_idx, pres2_idx, pres3_idx)))]
		
	div_13 = div_1 + div_3
	div_23 = div_2 + div_3
	gain_1_rescaled = gain_1 / (div_1 + 1.)
	gain_2_rescaled = gain_2 / (div_2 + 1.)
	gain_1_rescaled[np.isnan(gain_1_rescaled)] = np.nanmax(gain_1_rescaled)
	gain_2_rescaled[np.isnan(gain_2_rescaled)] = np.nanmax(gain_2_rescaled)
	div_13[-1] = sum(np.isin(data_temp[:,-1], [1., 3.]))
	div_23[-1] = sum(np.isin(data_temp[:,-1], [2., 3.]))
	
	div_13 = div_13[1:]
	div_23 = div_23[1:]
	gain_1_rescaled = gain_1_rescaled[1:]
	gain_2_rescaled = gain_2_rescaled[1:]

	return div_13, div_23, gain_1_rescaled, gain_2_rescaled, pres[1:,:]


# Calculate difference from a given diversity to the equilibrium diversity for two areas
# (in case of covariate dependent dispersal or extinction, 
# the equilibrium is calculated for the covariate mean)
def calc_diff_equil_two_areas(div): 
	div1 = div[0]
	div2 = div[1]
	div3 = div[2]
	div13 = div1 + div3
	div23 = div2 + div3
	if div13 > k_d[0] or div23 > k_d[1] or div13 >= k_e[0] or div23 >= k_e[1] or (div1 + div3 < 1) or (div2 + div3 < 1):
		diff_equil = 1e10
	else:
		lim_d2 = max(0, 1 - div13/k_d[0]) # Limit dispersal into area 2
		lim_d1 = max(0, 1 - div23/k_d[1]) # Limit dispersal into area 1
		gain1 = dis[1] * div2 * lim_d1
		gain2 = dis[0] * div1 * lim_d2
		if argsDdE: # Dispersal dependent extinction
			mu1 = ext[0] + covar_par[2] * gain1 / (div13 + 1.)
			mu2 = ext[1] + covar_par[3] * gain2 / (div23 + 1.)
		else: # Diversity dependent extinction
			lim_e1 = max(1e-10, 1 - div13/k_e[0]) # Increases extinction in area 2
			lim_e2 = max(1e-10, 1 - div23/k_e[1]) # Increases extinction in area 1
			mu1 = ext[0]/lim_e1
			mu2 = ext[1]/lim_e2
		loss1 = mu1 * div1 + mu1 * div3
		loss2 = mu2 * div2 + mu2 * div3
		diff_equil = abs(gain1 - loss1) + abs(gain2 - loss2)
	return diff_equil

# Calculate difference from a given diversity to the equilibrium diversity for one area	
def calc_diff_equil_one_area(div):
	div_both = div[0] + div[1]
	if div_both > k_d or div_both >= k_e or div_both < 1:
		diff_equil = 1e10
	else:
		lim_d = max(0, 1 - div_both/k_d)  # Limit dispersal into focal area
		gain = dis * div[0] * lim_d
		if argsDdE: # Dispersal dependent extinction
			mu = ext + covar_par_equil * gain / (div_both + 1.)
		else: # Diversity dependent extinction
			lim_e = max(1e-10, 1 - div_both/k_e)
			mu = ext/lim_e
		loss = mu * div_both
		diff_equil = abs(gain - loss)
	return diff_equil


def get_num_dispersals(dis_rate_vec,r_vec):
	Pr1 = 1- r_vec[Q_index[0:-1],1] # remove last value (time zero)
	Pr2 = 1- r_vec[Q_index[0:-1],2] 
	# get dispersal rates through time
	#d12 = dis_rate_vec[0][0] *exp(covar_par[0]*time_var)
	#d21 = dis_rate_vec[0][1] *exp(covar_par[1]*time_var)
	dr = dis_rate_vec
	d12 = dr[:,0]
	d21 = dr[:,1]
	
	numD12 = (div_traj_1/Pr1)*d12
	numD21 = (div_traj_2/Pr2)*d21
	
	return numD12,numD21

#def get_est_div_traj(r_vec):
#	Pr1 = 1- r_vec[Q_index[0:-1],1] # remove last value (time zero)
#	Pr2 = 1- r_vec[Q_index[0:-1],2] 
#	
#	numD1 = (div_traj_1/Pr1)
#	numD2 = (div_traj_2/Pr2)
#	numD1res = rescale_vec_to_range(numD1, r=10., m=0)
#	numD2res = rescale_vec_to_range(numD2, r=10., m=0)
#	
#	return numD1res,numD2res
	

# initialize weight per gamma cat per species to estimate diversity trajectory with heterogeneous preservation
weight_per_taxon = np.ones((nTaxa, pp_gamma_ncat)) / pp_gamma_ncat


def get_marginal_traitrate(baserate, nTaxa, pres, traits, cont_trait, cont_trait_par, cat, cat_trait, cat_trait_par):
	pres3D = pres.reshape(pres.shape[0], nTaxa, 3)
	abun_taxa = np.sum(pres3D, axis = 2)
	abun_taxa = abun_taxa / np.sum(abun_taxa, axis = 1).reshape(-1,1)
	baserate1 = baserate[:,0][::-1].reshape(-1,1)
	baserate2 = baserate[:,1][::-1].reshape(-1,1)
	if traits:
		cont_modi = np.exp(np.sum(cont_trait_par * cont_trait, axis = 1))
		rate_taxa1 = baserate1 * cont_modi
		rate_taxa2 = baserate2 * cont_modi
		baserate1 = rate_taxa1
		baserate2 = rate_taxa2
	if cat:
		cat_modi = np.sum(np.exp(cat_trait_par[cat_trait]), axis = 1)
		rate_taxa1 = baserate1 * cat_modi
		rate_taxa2 = baserate2 * cat_modi
	rate_taxa1 = rate_taxa1 * abun_taxa
	rate_taxa2 = rate_taxa2 * abun_taxa
	rate1 = np.sum(rate_taxa1, axis = 1)
	rate2 = np.sum(rate_taxa2, axis = 1)
	margrate = np.array([rate1, rate2])
	return(margrate)

###################################################################################
# Avoid code redundancy in mcmc and maximum likelihood
def lik_DES_taxon(args):
	[l, dis_vec, ext_vec, w_list, vl_list, vl_inv_list, Q_list, Q_index_temp,
	delta_t, r_vec, rho_at_present_LIST, r_vec_indexes_LIST, sign_list_LIST, OrigTimeIndex, Q_index, bin_last_occ,
	time_var_d1, time_var_d2, time_var_e1, time_var_e2, covar_par, covar_parD, covar_parE,
	x0_logisticD, x0_logisticE, transf_d, transf_e, offset_dis_div1, offset_dis_div2, offset_ext_div1, offset_ext_div2,
	traits, trait_parD, traitD, trait_parE, traitE, cat, cat_parD, catD, cat_parE, catE, use_Pade_approx] = args
	if traits or cat:
		if traits:
			dis_vec = dis_vec * np.exp(np.sum(trait_parD * traitD[l,:]))
			ext_vec = ext_vec * np.exp(np.sum(trait_parE * traitE[l,:]))
		if cat:
			dis_vec = dis_vec * np.sum(np.exp(cat_parD[catD][l,:]))
			ext_vec = ext_vec * np.sum(np.exp(cat_parE[catE][l,:]))
		Q_list, marginal_rates_temp = make_Q_Covar4VDdE(dis_vec, ext_vec,
								time_var_d1, time_var_d2, time_var_e1, time_var_e2,
								covar_par, covar_parD, covar_parE, x0_logisticD, x0_logisticE, transf_d, transf_e,
								offset_dis_div1, offset_dis_div2, offset_ext_div1, offset_ext_div2)
	if use_Pade_approx==0:
		w_list,vl_list,vl_inv_list = get_eigen_list(Q_list)
		l_temp = calc_likelihood_mQ_eigen([delta_t,r_vec,w_list,vl_list,vl_inv_list,rho_at_present_LIST[l],r_vec_indexes_LIST[l],sign_list_LIST[l],OrigTimeIndex[l],Q_index,Q_index_temp,bin_last_occ[l]])
	else:
		l_temp = calc_likelihood_mQ([delta_t,r_vec,Q_list,rho_at_present_LIST[l],r_vec_indexes_LIST[l],sign_list_LIST[l],OrigTimeIndex[l],Q_index,Q_index_temp,bin_last_occ[l]])
	return(l_temp)

# Start pool after defining function
if use_seq_lik is True: num_processes=0
if num_processes>0: pool_lik = multiprocessing.Pool(num_processes) # likelihood

def lik_DES(dis_vec, ext_vec, r_vec, time_var_d1, time_var_d2, time_var_e1, time_var_e2, covar_par, covar_parD, covar_parE, x0_logisticD, x0_logisticE, transf_d, transf_e, offset_dis_div1, offset_dis_div2, offset_ext_div1, offset_ext_div2, rho_at_present_LIST, r_vec_indexes_LIST, sign_list_LIST, OrigTimeIndex,Q_index, alpha, YangGammaQuant, pp_gamma_ncat, num_processes, use_Pade_approx, bin_last_occ, traits, trait_parD, traitD, trait_parE, traitE, cat, cat_parD, catD, catE, cat_parE):
	# weight per gamma cat per species: multiply 
	weight_per_taxon = np.zeros((nTaxa, pp_gamma_ncat))
	Q_list, marginal_rates_temp = make_Q_Covar4VDdE(dis_vec,ext_vec,
							time_var_d1,time_var_d2,time_var_e1,time_var_e2,
							covar_par, covar_parD, covar_parE, x0_logisticD, x0_logisticE, transf_d, transf_e,
							offset_dis_div1, offset_dis_div2, offset_ext_div1, offset_ext_div2)
	Q_index_temp = np.array(range(0,len(Q_list)))
	if num_processes==0:
		w_list,vl_list,vl_inv_list = get_eigen_list(Q_list)
		lik = 0
		if argsG is False:
			for l in list_taxa_index:
				lik += lik_DES_taxon([l, dis_vec, ext_vec, w_list, vl_list, vl_inv_list, Q_list, Q_index_temp, delta_t,
							r_vec,
							rho_at_present_LIST, r_vec_indexes_LIST, sign_list_LIST, OrigTimeIndex, Q_index, bin_last_occ,
							time_var_d1, time_var_d2, time_var_e1, time_var_e2, covar_par, covar_parD, covar_parE,
							x0_logisticD, x0_logisticE, transf_d, transf_e, offset_dis_div1, offset_dis_div2, offset_ext_div1, offset_ext_div2,
							traits, trait_parD, traitD, trait_parE, traitE, cat, cat_parD, catD, cat_parE, catE, use_Pade_approx])
		else:
			for l in list_taxa_index:
				YangGamma = get_gamma_rates(alpha, YangGammaQuant, pp_gamma_ncat)
				lik_vec = np.zeros(pp_gamma_ncat)
				for i in range(pp_gamma_ncat): 
					r_vec_Gamma = exp(-bin_size * YangGamma[i] * -log(r_vec)/bin_size) # convert to probability scale
					r_vec_Gamma[:,0] = 0
					r_vec_Gamma[:,3] = 1
					if args.data_in_area == 1:
						r_vec_Gamma[:,2] = small_number
					elif args.data_in_area == 2:
						r_vec_Gamma[:,1] = small_number
						Q_list, marginal_rates_temp= make_Q_Covar4VDdE(dis_vec,ext_vec,
												time_var_d1,time_var_d2,time_var_e1,time_var_e2,
												covar_par, covar_parD, covar_parE, x0_logisticD, x0_logisticE,transf_d,transf_e,
												offset_dis_div1, offset_dis_div2, offset_ext_div1, offset_ext_div2)
					w_list,vl_list,vl_inv_list = get_eigen_list(Q_list)
					lik_vec[i] = lik_DES_taxon([l,dis_vec, ext_vec, w_list, vl_list, vl_inv_list, Q_list, Q_index_temp, delta_t,
							r_vec_Gamma, # Only difference to homogeneous sampling
							rho_at_present_LIST, r_vec_indexes_LIST, sign_list_LIST, OrigTimeIndex, Q_index, bin_last_occ,
							time_var_d1, time_var_d2, time_var_e1, time_var_e2, covar_par, covar_parD, covar_parE,
							x0_logisticD, x0_logisticE, transf_d, transf_e, offset_dis_div1, offset_dis_div2, offset_ext_div1, offset_ext_div2,
							traits, trait_parD, traitD, trait_parE, traitE, cat, cat_parD, catD, cat_parE, catE, use_Pade_approx])
				lik_vec_max = np.max(lik_vec)
				lik2 = lik_vec - lik_vec_max
				lik += log(sum(exp(lik2))/pp_gamma_ncat) + lik_vec_max
				weight_per_taxon[l,:] = lik_vec / sum(lik_vec)
		#print "lik2", lik
		
			
	else: # multi=processing
		#sys.exit("Multi-threading not available")
		w_list,vl_list,vl_inv_list = get_eigen_list(Q_list)
		if argsG is False:
			args_mt_lik = [ [l, dis_vec, ext_vec, w_list, vl_list, vl_inv_list, Q_list, Q_index_temp, delta_t,
					r_vec,
					rho_at_present_LIST, r_vec_indexes_LIST, sign_list_LIST, OrigTimeIndex, Q_index, bin_last_occ,
					time_var_d1, time_var_d2, time_var_e1, time_var_e2, covar_par, covar_parD, covar_parE,
					x0_logisticD, x0_logisticE, transf_d, transf_e, offset_dis_div1, offset_dis_div2, offset_ext_div1, offset_ext_div2,
					traits, trait_par, traitD, traitE, cat, cat_parD, catD, cat_parE, catE, use_Pade_approx] for l in list_taxa_index ]
			lik = sum(np.array(pool_lik.map(lik_DES_taxon, args_mt_lik)))
		else:
			YangGamma = get_gamma_rates(alpha, YangGammaQuant, pp_gamma_ncat)
			liktmp = np.zeros((pp_gamma_ncat, nTaxa)) # row: ncat column: species
			for i in range(pp_gamma_ncat): 
				r_vec_Gamma = exp(-bin_size * YangGamma[i] * -log(r_vec)/bin_size) # convert to probability scale
				r_vec_Gamma[:,0] = 0
				r_vec_Gamma[:,3] = 1
				if data_in_area == 1:
					r_vec_Gamma[:,2] = small_number
				elif data_in_area == 2:
					r_vec_Gamma[:,1] = small_number
				args_mt_lik = [ [l,dis_vec, ext_vec, w_list, vl_list, vl_inv_list, Q_list, Q_index_temp, delta_t,
						r_vec_Gamma, # Only difference to homogeneous sampling
						rho_at_present_LIST, r_vec_indexes_LIST, sign_list_LIST, OrigTimeIndex, Q_index, bin_last_occ,
						time_var_d1, time_var_d2, time_var_e1, time_var_e2, covar_par, covar_parD, covar_parE,
						x0_logisticD, x0_logisticE, transf_d, transf_e, offset_dis_div1, offset_dis_div2, offset_ext_div1, offset_ext_div2,
						traits, trait_par, traitD, traitE, cat, catD, catE, use_Pade_approx] for l in list_taxa_index ]
				liktmp[i,:] = np.array(pool_lik.map(lik_DES_taxon, args_mt_lik))
			liktmpmax = np.amax(liktmp, axis = 0)
			liktmp2 = liktmp - liktmpmax
			lik = sum(log(sum( exp(liktmp2), axis = 0 )/pp_gamma_ncat)+liktmpmax)
			weight_per_taxon = liktmp / sum(liktmp, axis = 0)

	return lik, weight_per_taxon


# Likelihood for a set of parameters
def lik_opt(x, grad):
	covar_par = np.zeros(4) + 0.
	covar_parD = np.zeros(2 * num_varD) + 0.
	covar_parE = np.zeros(2 * num_varE) + 0.
	x0_logisticD = np.zeros(2 * num_varD) + 0.
	x0_logisticE = np.zeros(2 * num_varE) + 0.
	x0_logistic = np.zeros(4) + 0.
	# Sampling
	r_vec = np.zeros((n_Q_times,nareas+2)) 
	r_vec[:,3]=1
	if data_in_area == 1:
		r_vec[:,1] = x[opt_ind_r_vec]
		r_vec[:,2] = small_number
	elif data_in_area == 2:
		r_vec[:,1] = small_number
		r_vec[:,2] = x[opt_ind_r_vec]
	elif constraints_45:
		constraints_45_which = constraints_covar[constraints_covar > 3]
		if sum(constraints_45_which) == 4 and len(constraints_45_which) == 1:
			r_vec[:,1] = np.array(x[opt_ind_r_vec[0]])
			r_vec[:,2] = np.array(x[opt_ind_r_vec[1:]])
		elif sum(constraints_45_which) == 5 and len(constraints_45_which) == 1:
			r_vec[:,1] = np.array(x[opt_ind_r_vec[:-1]])
			r_vec[:,2] = np.array(x[opt_ind_r_vec[-1]])
		else:
			r_vec[:,1] = np.array(x[opt_ind_r_vec[0]])
			r_vec[:,2] = np.array(x[opt_ind_r_vec[1]])
	else:
		r_vec[:,1:3] = np.array(x[opt_ind_r_vec]).reshape(n_Q_times,nareas)
	# Dispersal
	dis_vec = np.zeros((n_Q_times,nareas))
	if data_in_area == 1:
		dis_vec[:,1] = x[opt_ind_dis]
	elif data_in_area == 2:
		dis_vec[:,0] = x[opt_ind_dis]
	elif constraints_01 and args.TdD:
		constraints_01_which = constraints_covar[constraints_covar < 2]
		# Both dispersal rates could be constant!
		if sum(constraints_01_which) == 0 and len(constraints_01_which) == 1:
			dis_vec[:,0] = np.array(x[opt_ind_dis[0]])
			dis_vec[:,1] = np.array(x[opt_ind_dis[1:]])
		elif sum(constraints_01_which) == 1 and len(constraints_01_which) == 1:
			dis_vec[:,0] = np.array(x[opt_ind_dis[:-1]])
			dis_vec[:,1] = np.array(x[opt_ind_dis[-1]])
		else:
			dis_vec[:,0] = np.array(x[opt_ind_dis[0]])
			dis_vec[:,1] = np.array(x[opt_ind_dis[1]])
	else:
		dis_vec = np.array(x[opt_ind_dis]).reshape(n_Q_times_dis,nareas)
		
	do_approx_div_traj = 0
	if args.TdD: # time dependent D
		dis_vec = dis_vec[Q_index,:] 
		dis_vec = dis_vec[0:-1] 
		transf_d = 0
		time_var_d1,time_var_d2=time_varD,time_varD
	elif do_DivdD: # Diversity dependent D
		transf_d = 4 # 1
		#time_var_d1,time_var_d2 = get_est_div_traj(r_vec)
		do_approx_div_traj = 1
	else: # temp dependent D
		transf_d=1
		time_var_d1,time_var_d2=time_varD,time_varD
	if args.lgD: transf_d = 2
	
	# Extinction
	ext_vec = np.zeros((n_Q_times,nareas))
	if data_in_area == 1:
		ext_vec[:,0] = x[opt_ind_ext]
	elif data_in_area == 2:
		ext_vec[:,1] = x[opt_ind_ext]
	elif constraints_23 and args.TdE:
		constraints_23_which = constraints_covar[np.logical_and(constraints_covar >= 2, constraints_covar < 4)]
		if sum(constraints_23_which) == 2 and len(constraints_23_which) == 1:
			ext_vec[:,0] = np.array(x[opt_ind_ext[0]])
			ext_vec[:,1] = np.array(x[opt_ind_ext[1:]])
		elif sum(constraints_23_which) == 3 and len(constraints_23_which) == 1:
			ext_vec[:,0] = np.array(x[opt_ind_ext[:-1]])
			ext_vec[:,1] = np.array(x[opt_ind_ext[-1]])
		else:
			ext_vec[:,0] = np.array(x[opt_ind_ext[0]])
			ext_vec[:,1] = np.array(x[opt_ind_ext[1]])
	else:
		ext_vec = np.array(x[opt_ind_ext]).reshape(n_Q_times_ext,nareas)
	if args.TdE:
		ext_vec = ext_vec[Q_index,:] 
		ext_vec = ext_vec[0:-1] 
		transf_e = 0
		time_var_e1,time_var_e2=time_varD,time_varD
	elif do_DivdE: # Diversity dep Extinction
		# NOTE THAT extinction in 1 depends diversity in 1
		transf_e = 4
		#time_var_e1,time_var_e2 = get_est_div_traj(r_vec)
		do_approx_div_traj = 1
	elif args.DdE: # Dispersal dep Extinction
		transf_e = 3
		do_approx_div_traj = 1
	else: # Temp dependent Extinction
		transf_e = 1
		time_var_e1,time_var_e2=time_varE,time_varE
	if args.lgE: transf_e = 2
		
	alpha = 10.
	if argsG:
		alpha = x[alpha_ind]
	
	if transf_d > 0:
		if transf_d == 1 or transf_d == 2:
			if do_symCovD:
				x_covD = x[opt_ind_covar_dis]
				x_covD = x_covD[idx_symCovD]
				covar_parD = x_covD
			else:
				covar_parD = x[opt_ind_covar_dis]
		else: covar_par[[0,1]] = x[opt_ind_covar_dis]
		if transf_d == 2:
			if do_symCovD:
				x0_covD = x[opt_ind_x0_log_dis]
				x0_covD = x0_covD[idx_symCovD]
				x0_logisticD = x_covD
			else:
				x0_logisticD = x[opt_ind_x0_log_dis]
	if transf_e > 0:
		if transf_e == 1 or transf_e == 2:
			if do_symCovE:
				x_covE = x[opt_ind_covar_ext]
				x_covE = x_covE[idx_symCovE]
				covar_parE = x_covE
			else:
				covar_parE = x[opt_ind_covar_ext]
		else: covar_par[[2,3]] = x[opt_ind_covar_ext]
		if transf_e == 2:
			if do_symCovE:
				x0_covE = x[opt_ind_x0_log_ext]
				x0_covE = x0_covE[idx_symCovE]
				x0_logisticE = x0_covE
			else:
				x0_logisticE = x[opt_ind_x0_log_ext]
	
	# enforce constraints if any
	if constraints_covar_true:
		covar_par[constraints_covar[constraints_covar<4]] = 0
		x0_logistic[constraints_covar[constraints_covar<4]] = 0
	# Trait-dependence
	trait_parD = np.zeros(num_traitD) + 0.
	trait_parE = np.zeros(num_traitE) + 0.
	if argstraitD != "":
		trait_parD = x[opt_ind_trait_dis]
	if argstraitE != "":
		trait_parE = x[opt_ind_trait_ext]
	# Categories
	cat_parD = np.ones(len(unique_catD))
	cat_parE = np.ones(len(unique_catE))
	if argscatD != "":
		cat_parD[catD_not_baseline] = x[opt_ind_cat_dis]
	if argscatE != "":
		cat_parE[catE_not_baseline] = x[opt_ind_cat_ext]

	approx_d1,approx_d2,numD21,numD12,pres = approx_div_traj(nTaxa, dis_vec, ext_vec,
								do_DivdD, do_DivdE, do_varD, do_varE, argsDdE, argsG,
								r_vec, alpha, YangGammaQuant, pp_gamma_ncat, bin_size, Q_index, Q_index_first_occ,
								covar_par, covar_parD, covar_parE, offset_dis_div1, offset_dis_div2, offset_ext_div1, offset_ext_div2,
								time_series, len_time_series, bin_first_occ, first_area, time_varD, time_varE, data_temp,
								trait_parD, traitD, trait_parE, traitE,
								cat_parD, catD, cat_parE, catE, argstraitD, argstraitE, argscatD, argscatE)
	if do_DivdD:
		time_var_d2 = approx_d1 # Limits dispersal into 1
		time_var_d1 = approx_d2 # Limits dispersal into 2
	if do_DivdE:
		time_var_e1 = approx_d1
		time_var_e2 = approx_d2
	if args.DdE:
		time_var_e2 = numD12
		time_var_e1 = numD21
	
#	est_div_gr_obs = all(approx_d1[:-1] - div_traj_1[1:] >= 0) and all(approx_d2[:-1] - div_traj_2[1:] >= 0)
#	est_div_gr_obs = sum(approx_d1[:-1] - div_traj_1[1:] >= -0.1) > (0.95 * len(div_traj_1[1:])) and sum(approx_d2[:-1] - div_traj_2[1:] >= -0.1) > (0.95 * len(div_traj_2[1:]))
	est_div_gr_obs = True
	# Backpropagation for likelihood calculation before the first observation
#	occ_prob = np.mean(r_vec[:,1:3], axis = 1)**(1 + np.arange(len_time_series))
#	print(occ_prob)
#	backpropagate = np.min(np.where(occ_prob < 0.5)) + 1
#	OrigTimeIndex2 = OrigTimeIndex - backpropagate
#	OrigTimeIndex2[OrigTimeIndex2 < 1] = 1
#	print(OrigTimeIndex2)

	if est_div_gr_obs:
		lik, weight_per_taxon = lik_DES(dis_vec, ext_vec, r_vec,
						time_var_d1, time_var_d2, time_var_e1, time_var_e2,
						covar_par, covar_parD, covar_parE, x0_logisticD, x0_logisticE, transf_d, transf_e,
						offset_dis_div1, offset_dis_div2, offset_ext_div1, offset_ext_div2,
						rho_at_present_LIST, r_vec_indexes_LIST, sign_list_LIST,OrigTimeIndex,
						Q_index, alpha, YangGammaQuant, pp_gamma_ncat, num_processes, use_Pade_approx, bin_last_occ,
						traits, trait_parD, traitD, trait_parE, traitE, cat, cat_parD, catD, catE, cat_parE)
	else:
		lik = -np.inf#1e15
	print("lik", lik, x)
	return lik

# Maximize likelihood
if args.A == 3:
	n_generations   = 1
	sampling_freq   = 1
	print_freq      = 1
	# Define which initial value for the optimizer corresponds to which parameter
	# opt_ind_xxx: indices for parameters to optimize
	# x0: initial values
	# xxx_bounds: bounds for optimization
	
	if args.TdD is True:
		n_Q_times_dis = n_Q_times
	else:
		n_Q_times_dis = 1
	opt_ind_dis = np.arange(0, n_Q_times_dis*nareas) 
	if equal_d is True:
		opt_ind_dis = np.repeat(np.arange(0, n_Q_times_dis), 2)
	if data_in_area != 0:
		opt_ind_dis = np.arange(0, n_Q_times_dis)
	if args.TdD is True and constraints_01: 
		if len(constraints_covar[constraints_covar < 2]) == 1:
			opt_ind_dis = np.arange(0, n_Q_times_dis + 1)
		else:
			opt_ind_dis = np.arange(0, nareas)
	
	if args.TdE is True:
		n_Q_times_ext = n_Q_times
	else:
		n_Q_times_ext = 1
	opt_ind_ext = np.max(opt_ind_dis) + 1 + np.arange(0, n_Q_times_ext*nareas) 
	if equal_e is True:
		opt_ind_ext = np.max(opt_ind_dis) + 1 + np.repeat(np.arange(0, n_Q_times_ext), 2)
	if data_in_area != 0:
		opt_ind_ext = np.max(opt_ind_dis) + 1 + np.arange(0, n_Q_times_ext)
	if args.TdE is True and constraints_23:
		if all(np.isin(np.array([2, 3]), constraints_covar)):
			opt_ind_ext = np.max(opt_ind_dis) + 1 + np.arange(0, nareas)
		else:
			opt_ind_ext = np.max(opt_ind_dis) + 1 + np.arange(0, n_Q_times_ext + 1)
	
	opt_ind_r_vec = np.max(opt_ind_ext) + 1 + np.arange(0, n_Q_times*nareas)
	if equal_q is True:
		opt_ind_r_vec = np.max(opt_ind_ext) + 1 + np.repeat(np.arange(0, n_Q_times), 2) 
	if const_q ==1: # Needs bin1 = 01 bin2 = 02 bin3 = 03 bin4 = 04 bin5 = 05
		opt_ind_r_vec = np.max(opt_ind_ext) + 1 + np.array([np.zeros(nareas, dtype = int), np.arange(1,nareas+1)]).T.flatten()
	if const_q ==2: # Needs bin1 = 01 bin2 = 21 bin3 = 31 bin4 = 41 bin5 = 51
		opt_ind_r_vec = np.array([np.arange(1,nareas+1), np.ones(nareas, dtype = int)]).T.flatten()
		opt_ind_r_vec[0] = 0
		opt_ind_r_vec = np.max(opt_ind_ext) + 1 + opt_ind_r_vec
	if constraints_45:
		if all(np.isin(np.array([4, 5]), constraints_covar)):
			opt_ind_r_vec = np.max(opt_ind_ext) + 1 + np.arange(0, nareas)
		else:
			opt_ind_r_vec = np.max(opt_ind_ext) + 1 + np.arange(0, n_Q_times + 1)
	if data_in_area != 0:
		if const_q ==1 or const_q ==2:
			opt_ind_r_vec = np.max(opt_ind_ext) + 1 + np.zeros(n_Q_times, dtype = int)
		else: 
			opt_ind_r_vec = np.max(opt_ind_ext) + 1 + np.arange(0, n_Q_times)
	
	
	x0 = np.zeros(1 + np.max(opt_ind_r_vec)) # Initial values
	x0[opt_ind_dis] = np.random.uniform(0.1,0.2, len(opt_ind_dis))
	x0[opt_ind_ext] = np.random.uniform(0.01,0.05, len(opt_ind_ext))
	x0[opt_ind_r_vec] = np.random.uniform(0.1,0.5, len(opt_ind_r_vec))
	lower_bounds = [small_number]*len(x0)
	upper_bounds = [100]*len(x0)
	upper_bounds[-len(opt_ind_r_vec):] = [1 - small_number] * len(opt_ind_r_vec)
	
	# Preservation heterogeneity
	ind_counter = np.max(opt_ind_r_vec) + 1 
	if argsG:
		alpha_ind = ind_counter
		ind_counter += 1
		x0 = np.concatenate((x0, 10.), axis = None) 
		lower_bounds = lower_bounds + [small_number]
		upper_bounds = upper_bounds + [100]
		
	# Covariates
	if args.TdD is False or do_DivdD:
		if do_varD:
			opt_ind_covar_dis = np.arange(ind_counter, ind_counter + 2 * num_varD)
			ind_counter += 2 * num_varD
			x0 = np.concatenate((x0, np.zeros(2 * num_varD)), axis = None)
			lower_bounds = lower_bounds + (-bound_covar_d).tolist() + (-bound_covar_d).tolist()
			upper_bounds = upper_bounds + (bound_covar_d).tolist() + (bound_covar_d).tolist()
		if do_DivdD: # Conflict with args.varD!
			opt_ind_covar_dis = np.array([ind_counter, ind_counter + 1])
			ind_counter += 2
			x0 = np.concatenate((x0, nTaxa + 0., nTaxa + 0.), axis = None)
			lower_bounds = lower_bounds + [np.max(div_traj_2)] + [np.max(div_traj_1)]
			upper_bounds = upper_bounds + [np.inf] + [np.inf]
		if do_symCovD or data_in_area != 0 or constraints_01:
			until = 1
			if do_symCovD:
				until = len(symCovD)
			opt_ind_covar_dis = opt_ind_covar_dis[0:-until]
			ind_counter = ind_counter - until
			x0 = x0[0:-until]
			lower_bounds = lower_bounds[0:-until]
			upper_bounds = upper_bounds[0:-until]
			if do_DivdD:
				lower_bounds[-1] = np.max((np.max(div_traj_2), np.max(div_traj_1)))
		if args.lgD:
			opt_ind_x0_log_dis = np.arange(ind_counter, ind_counter + 2 * num_varD)
			ind_counter += 2 * num_varD
			x0 = np.concatenate((x0, np.mean(time_varD, axis = 0), np.mean(time_varD, axis = 0)), axis = None)
			lower_bounds = lower_bounds + np.min(time_varD, axis = 0).tolist() + np.min(time_varD, axis = 0).tolist()
			upper_bounds = upper_bounds + np.max(time_varD, axis = 0).tolist() + np.max(time_varD, axis = 0).tolist()
			if do_symCovD or data_in_area != 0 or constraints_01:
				until = 1
				if do_symCovD:
					until = len(symCovD)
				opt_ind_x0_log_dis = opt_ind_x0_log_dis[0:-until]
				ind_counter = ind_counter - until
				x0 = x0[0:-until]
				lower_bounds = lower_bounds[0:-until]
				upper_bounds = upper_bounds[0:-until]
	
	if args.TdE is False or do_DivdE or argsDdE:
		if args.varE != "":
			opt_ind_covar_ext = np.arange(ind_counter, ind_counter + 2 * num_varE)
			ind_counter += 2 * num_varE
			x0 = np.concatenate((x0, np.zeros(2 * num_varE)), axis = None)
			lower_bounds = lower_bounds + (-bound_covar_e).tolist() + (-bound_covar_e).tolist()
			upper_bounds = upper_bounds + bound_covar_e.tolist() + bound_covar_e.tolist()
		if do_DivdE: # Conflict with args.varE!
			opt_ind_covar_ext = np.array([ind_counter, ind_counter + 1])
			ind_counter += 2
			x0 = np.concatenate((x0, nTaxa + 0., nTaxa + 0.), axis = None)
			lower_bounds = lower_bounds + [np.max(div_traj_1)] + [np.max(div_traj_2)]
			upper_bounds = upper_bounds + [np.inf] + [np.inf]
		elif argsDdE: # Conflict with args.varE!
			opt_ind_covar_ext = np.array([ind_counter, ind_counter + 1])
			ind_counter += 2
			x0 = np.concatenate((x0, 0., 0.), axis = None)
			lower_bounds = lower_bounds + [0.] + [0.]
			upper_bounds = upper_bounds + [50.] + [50.]
		if do_symCovE or data_in_area != 0 or constraints_23:
			until = 1
			if do_symCovE:
				until = len(symCovE)
			opt_ind_covar_ext = opt_ind_covar_ext[0:-until]
			ind_counter = ind_counter - until
			x0 = x0[0:-until]
			lower_bounds = lower_bounds[0:-until]
			upper_bounds = upper_bounds[0:-until]
			if do_DivdE:
				lower_bounds[-1] = np.max((np.max(div_traj_2), np.max(div_traj_1)))
		if args.lgE:
			opt_ind_x0_log_ext = np.arange(ind_counter, ind_counter + 2 * num_varE)
			ind_counter += 2 * num_varE
			x0 = np.concatenate((x0, np.mean(time_varE), np.mean(time_varE)), axis = None)
			lower_bounds = lower_bounds + np.min(time_varE, axis = 0).tolist() + np.min(time_varE, axis = 0).tolist()
			upper_bounds = upper_bounds + np.max(time_varE, axis = 0).tolist() + np.max(time_varE, axis = 0).tolist()
			if do_symCovE or data_in_area != 0 or constraints_23:
				until = 1
				if do_symCovE:
					until = len(symCovE)
				opt_ind_x0_log_ext = opt_ind_x0_log_ext[0:-until]
				ind_counter = ind_counter - until
				x0 = x0[0:-until]
				lower_bounds = lower_bounds[0:-until]
				upper_bounds = upper_bounds[0:-until]
	
	# Trait-dependence
	if argstraitD != "":
		opt_ind_trait_dis = np.arange(ind_counter, ind_counter + num_traitD)
		ind_counter += num_traitD
		x0 = np.concatenate((x0, np.zeros(num_traitD)), axis = None)
		lower_bounds = lower_bounds + (-bound_traitD).tolist()
		upper_bounds = upper_bounds + bound_traitD.tolist()
	if argstraitE != "":
		opt_ind_trait_ext = np.arange(ind_counter, ind_counter + num_traitE)
		ind_counter += num_traitE
		x0 = np.concatenate((x0, np.zeros(num_traitE)), axis = None)
		lower_bounds = lower_bounds + (-bound_traitE).tolist()
		upper_bounds = upper_bounds + (bound_traitE).tolist()
	# Categories
	if argscatD != "":
		len_catD = len(unique_catD) - len(num_catD) # Deviation from a common mean
		opt_ind_cat_dis = np.arange(ind_counter, ind_counter + len_catD)
		ind_counter += len_catD
		x0 = np.concatenate((x0, np.zeros(len_catD)), axis = None)
		lower_bounds = lower_bounds + [-5] * len_catD
		upper_bounds = upper_bounds + [3] * len_catD
	if argscatE != "":
		len_catE = len(unique_catE) - len(num_catE) # Deviation from a common mean
		opt_ind_cat_ext = np.arange(ind_counter, ind_counter + len_catE)
		ind_counter += len_catE
		x0 = np.concatenate((x0, np.zeros(len_catE)), axis = None)
		lower_bounds = lower_bounds + [-5] * len_catE
		upper_bounds = upper_bounds + [3] * len_catE
		
	if len(args.A3init) > 0:
		A3init = np.array(args.A3init)
		A3init[opt_ind_r_vec] = np.exp(-A3init[opt_ind_r_vec] * bin_size)
		if do_DivdD:
			A3init[opt_ind_dis] = A3init[opt_ind_dis] * (1. - ([offset_dis_div2, offset_dis_div1] / A3init[opt_ind_covar_dis]))
		if do_DivdE:
			A3init[opt_ind_ext] = A3init[opt_ind_ext] / (1. - ([offset_ext_div2, offset_ext_div1]/A3init[opt_ind_covar_ext]))
		x0 = A3init


	# Maximize likelihood
	if args.A3set[4] == 1 and any(args.TdD is False or do_DivdD or args.TdE is False or do_DivdE or args.DdE or (data_in_area != 0 and argsG) or argstraitD != "" or argstraitE != "" or argscatD != "" or argscatE != ""):
		print("Optimize only baseline dispersal, extinction and sampling")
		args.A3set[2] = args.A3set[2] / 2
		args.A3set[3] = args.A3set[3] / 2
		opt_base = nlopt.opt(nlopt.LN_SBPLX, len(x0))
		new_lower_bounds = lower_bounds[:]
		new_upper_bounds = upper_bounds[:]
		frombound = int(max(opt_ind_r_vec)) + 1
		tobount = len(x0)
		if argsG and data_in_area == 0:
			frombound = frombound + 1
		new_lower_bounds[frombound:tobount] = x0[frombound:tobount]
		new_upper_bounds[frombound:tobount] = x0[frombound:tobount]
		if do_DivdD:
			for i in range(len(opt_ind_covar_dis)):
				fix_covar = int(opt_ind_covar_dis[i])
				new_lower_bounds[fix_covar] = nTaxa * 10
				new_upper_bounds[fix_covar] = nTaxa * 10
				x0[fix_covar] = nTaxa * 10
		if do_DivdE:
			for i in range(len(opt_ind_covar_ext)):
				fix_covar = int(opt_ind_covar_ext[i])
				new_lower_bounds[fix_covar] = nTaxa * 10
				new_upper_bounds[fix_covar] = nTaxa * 10
				x0[fix_covar] = nTaxa * 10
		opt_base.set_lower_bounds(new_lower_bounds)
		opt_base.set_upper_bounds(new_upper_bounds)
		opt_base.set_max_objective(lik_opt)
		opt_base.set_xtol_rel(args.A3set[0])
		opt_base.set_maxeval(int(args.A3set[2])  * round(1.25**len(x0)))
		opt_base.set_ftol_abs(args.A3set[1])
		opt_base.set_maxtime(args.A3set[3])
		x_base = opt_base.optimize(x0)
		x0 = x_base
		print("Baseline dispersal, extinction and sampling optimized")
		if do_DivdD:
			for i in range(len(opt_ind_covar_dis)):
				fix_covar = int(opt_ind_covar_dis[i])
				x0[fix_covar] = nTaxa
		if do_DivdE:
			for i in range(len(opt_ind_covar_ext)):
				fix_covar = int(opt_ind_covar_ext[i])
				x0[fix_covar] = nTaxa
	if args.A3set[4] == 1 and args.TdD is False and args.TdE is False:
		args.A3set[2] = args.A3set[2] / 2
		args.A3set[3] = args.A3set[3] / 2
		opt_dis_cov = nlopt.opt(nlopt.LN_SBPLX, len(x0))
		new_lower_bounds2 = lower_bounds[:]
		new_upper_bounds2 = upper_bounds[:]
		frombound = int(max(opt_ind_covar_dis)) + 1
		if args.lgD:
			frombound = int(max(opt_ind_x0_log_dis)) + 1
		tobount = len(x0)
		new_lower_bounds2[frombound:tobount] = x0[frombound:tobount]
		new_upper_bounds2[frombound:tobount] = x0[frombound:tobount]
		if do_DivdE:
			for i in range(len(opt_ind_covar_ext)):
				fix_covar = int(opt_ind_covar_ext[i])
				new_lower_bounds2[fix_covar] = nTaxa * 10
				new_upper_bounds2[fix_covar] = nTaxa * 10
				x0[fix_covar] = nTaxa * 10
		opt_dis_cov.set_lower_bounds(new_lower_bounds2)
		opt_dis_cov.set_upper_bounds(new_upper_bounds2)
		opt_dis_cov.set_max_objective(lik_opt)
		opt_dis_cov.set_xtol_rel(args.A3set[0])
		opt_dis_cov.set_maxeval(int(args.A3set[2]) * round(1.25**len(x0)))
		opt_dis_cov.set_ftol_abs(args.A3set[1])
		opt_dis_cov.set_maxtime(args.A3set[3])
		x_dis_cov = opt_dis_cov.optimize(x0)
		x0 = x_dis_cov
	print("Final optimization")
	opt = nlopt.opt(nlopt.LN_SBPLX, len(x0))
	opt.set_lower_bounds(lower_bounds)
	opt.set_upper_bounds(upper_bounds)
	opt.set_max_objective(lik_opt)
	opt.set_xtol_rel(args.A3set[0])
	opt.set_maxeval(int(args.A3set[2]) * round(1.25**len(x0)))
	opt.set_ftol_abs(args.A3set[1])
	opt.set_maxtime(args.A3set[3])
	x = opt.optimize(x0)
	minf = opt.last_optimum_value()
	
	# Format output
	dis_rate_vec = np.zeros((n_Q_times_dis,nareas))
	if data_in_area == 1:
		dis_rate_vec[:,1] = x[opt_ind_dis]
	elif data_in_area == 2:
		dis_rate_vec[:,0] = x[opt_ind_dis]
	elif constraints_01 and args.TdD:
		constraints_01_which = constraints_covar[constraints_covar<2]
		# Both dispersal rates could be constant!
		if sum(constraints_01_which) == 0 and len(constraints_01_which) == 1:
			dis_rate_vec[:,0] = np.array(x[opt_ind_dis[0]])
			dis_rate_vec[:,1] = np.array(x[opt_ind_dis[1:]]) 
		elif sum(constraints_01_which) == 1 and len(constraints_01_which) == 1:
			dis_rate_vec[:,0] = np.array(x[opt_ind_dis[:-1]])
			dis_rate_vec[:,1] = np.array(x[opt_ind_dis[-1]])
		else:
			dis_rate_vec[:,0] = np.array(x[opt_ind_dis[0]])
			dis_rate_vec[:,1] = np.array(x[opt_ind_dis[1]])
	else:
		dis_rate_vec = np.array(x[opt_ind_dis]).reshape(n_Q_times_dis,nareas)
		
	ext_rate_vec = np.zeros((n_Q_times_ext,nareas))
	if data_in_area == 1:
		ext_rate_vec[:,0] = x[opt_ind_ext]
	elif data_in_area == 2:
		ext_rate_vec[:,1] = x[opt_ind_ext]
	elif constraints_23 and args.TdE:
		constraints_23_which = constraints_covar[np.logical_and(constraints_covar >= 2, constraints_covar < 4)]
		if sum(constraints_23_which) == 2 and len(constraints_23_which) == 1:
			ext_rate_vec[:,0] = np.array(x[opt_ind_ext[0]])
			ext_rate_vec[:,1] = np.array(x[opt_ind_ext[1:]])
		elif sum(constraints_23_which) == 3 and len(constraints_23_which) == 1:
			ext_rate_vec[:,0] = np.array(x[opt_ind_ext[:-1]])
			ext_rate_vec[:,1] = np.array(x[opt_ind_ext[-1]])
		else:
			ext_rate_vec[:,0] = np.array(x[opt_ind_ext[0]])
			ext_rate_vec[:,1] = np.array(x[opt_ind_ext[1]])
	else:
		ext_rate_vec = np.array(x[opt_ind_ext]).reshape(n_Q_times_ext,nareas)
		
	r_vec = np.zeros((n_Q_times,nareas+2))
	r_vec[:,3]=1
	if data_in_area == 1:
		r_vec[:,1] = x[opt_ind_r_vec]
		r_vec[:,2] = small_number
	elif data_in_area == 2:
		r_vec[:,1] = small_number
		r_vec[:,2] = x[opt_ind_r_vec]
	elif constraints_45:
		constraints_45_which = constraints_covar[constraints_covar > 3]
		if sum(constraints_45_which) == 4 and len(constraints_45_which) == 1:
			r_vec[:,1] = np.array(x[opt_ind_r_vec[0]])
			r_vec[:,2] = np.array(x[opt_ind_r_vec[1:]])
		elif sum(constraints_45_which) == 5 and len(constraints_45_which) == 1:
			r_vec[:,1] = np.array(x[opt_ind_r_vec[:-1]])
			r_vec[:,2] = np.array(x[opt_ind_r_vec[-1]])
		else:
			r_vec[:,1] = x[opt_ind_r_vec[0]]
			r_vec[:,2] = x[opt_ind_r_vec[1]]
	else:
		r_vec[:,1:3] = np.array(x[opt_ind_r_vec]).reshape(n_Q_times,nareas)
	if argsG: 
		alpha = x[alpha_ind]
		alpha = alpha.flatten()
	covar_par_A = np.zeros(4) + 0.
	x0_logistic_A = np.zeros(4) + 0.
	if do_varD:
		if do_symCovD:
			x_covD = x[opt_ind_covar_dis]
			x_covD = x_covD[idx_symCovD]
			covar_parD_A = x_covD
		else:
			covar_parD_A = x[opt_ind_covar_dis]
		if args.lgD:
			if do_symCovD:
				x0_covD = x[opt_ind_x0_log_dis]
				x0_covD = x0_covD[idx_symCovD]
				x0_logisticD_A = x0_covD
			else:
				x0_logisticD_A = x[opt_ind_x0_log_dis]
	if do_DivdD:
		covar_par_A[[0,1]] = x[opt_ind_covar_dis]
	if do_varE:
		if do_symCovE:
			x_covE = x[opt_ind_covar_ext]
			x_covE = x_covE[idx_symCovE]
			covar_parE_A = x_covE
		else:
			covar_parE_A = x[opt_ind_covar_ext]
		if args.lgE:
			if do_symCovE:
				x0_covE = x[opt_ind_x0_log_ext]
				x0_covE = x0_covE[idx_symCovE]
				x0_logisticE_A = x0_covE
			else:
				x0_logisticE_A = x[opt_ind_x0_log_ext]
	if do_DivdE or args.DdE:
		covar_par_A[[2,3]] = x[opt_ind_covar_ext]

	# Trait-dependence
	trait_par = np.zeros(2) + 0.
	if argstraitD != "":
		trait_parD_A = x[opt_ind_trait_dis]
	if argstraitE != "":
		trait_parE_A = x[opt_ind_trait_ext]
	# Categories
	if argscatD != "":
		cat_parD_A[catD_not_baseline] = x[opt_ind_cat_dis]
	if argscatE != "":
		cat_parE_A[catE_not_baseline] = x[opt_ind_cat_ext]
	log_to_file = 1

#############################################
do_approx_div_traj = 0
ml_it=0
scal_fac_ind=0

m_d = -3
M_d = 3
m_e = -3
M_e = 3
scale_proposal_d = 1
scale_proposal_e = 1
if args.TdD is False:
	scale_proposal_d = bound_covar_d/3.
	m_d = -bound_covar_d
	M_d = bound_covar_d
if do_DivdD:
	b = np.maximum(np.max(div_traj_2), np.max(div_traj_1))
	scale_proposal_divdd = b + 0.
	m_d = b
	M_d = np.inf
if args.TdE is False:
	scale_proposal_e = bound_covar_e/3.
	m_e = -bound_covar_e
	M_e = bound_covar_e
if do_DivdE:
	b = np.maximum(np.max(div_traj_2), np.max(div_traj_1))
	scale_proposal_divde = b + 0.
	m_e = b
	M_e = np.inf
	offset_ext_div1 = 0.
	offset_ext_div2 = 0.
if argsDdE:
	scale_proposal_divde = 5
	m_e = 0.
	M_e = 50.
if argstraitD != "":
	scale_proposal_a_d = bound_traitD/3.
	m_a_d = -bound_traitD
	M_a_d = bound_traitD
if argstraitE != "":
	scale_proposal_a_e = bound_traitE/3.
	m_a_e = -bound_traitE
	M_a_e = bound_traitE

for it in range(n_generations * len(scal_fac_TI)):
	if (it+1) % (n_generations+1) ==0: 
		print(it, n_generations)
		scal_fac_ind+=1
	if it ==0: 
		dis_rate_vec_A= dis_rate_vec
		ext_rate_vec_A= ext_rate_vec
		r_vec_A= r_vec 
		# fixed starting values 
		# dis_rate_vec_A= np.array([[0.032924117],[0.045818755]]).T #dis_rate_vec
		# ext_rate_vec_A= np.array([[0.446553889],[0.199597008]]).T #ext_rate_vec
		# covar_par_A=np.array([-0.076944388,-0.100211345,-0.161531353,-0.059495477])
		# r_vec_A=     exp(-np.array([0,1.548902792,1.477082486,1,0,1.767267039,1.981165598,1,0,2.726853331,3.048116889,1])*.5).reshape(3,4) # r_vec  
		likA=-inf
		priorA=-inf
		alphaA = alpha
	
	dis_rate_vec = dis_rate_vec_A + 0.
	ext_rate_vec = ext_rate_vec_A + 0.
	covar_par = covar_par_A + 0.
	covar_parD = covar_parD_A + 0.
	covar_parE = covar_parE_A + 0.
	trait_parD = trait_parD_A + 0.
	trait_parE = trait_parE_A + 0.
	cat_parD = cat_parD_A + 0.
	cat_parE = cat_parE_A + 0.
	r_vec = r_vec_A + 0.
	x0_logistic = x0_logistic_A + 0.
	x0_logisticD = x0_logisticD_A + 0.
	x0_logisticE = x0_logisticE_A + 0.
	hasting_de = 0
	hasting_alpha = 0
	hasting_catD = 0
	hasting_catE = 0
	hp_catD = hp_catD_A + 0.
	hp_catE = hp_catE_A + 0.
	gibbs_sample = 0
	if it>0: 
		if runMCMC == 1:
			r= np.random.random(4)
		elif it % 10==0:
			r= np.random.random(4)
	else: r = np.ones(4)+1
	
	if it<100: r[1]=1
	
	if r[0] < update_freq[0]: # DISPERSAL UPDATES
		if args.TdD is False and r[1] < .5: # update covar
			if args.lgD and r[2] < .5: # update logistic mid point
				x0_logisticD = update_parameter_uni_2d_freq(x0_logisticD_A,d=0.1*scale_proposal,f=0.5,m=-3,M=3)
			else:	
				if do_DivdD: covar_par[0:2] = update_parameter_uni_2d_freq(covar_par_A[0:2], d=scale_proposal_divdd, f=0.5, m = m_d, M = M_d)
				if do_DivdE or argsDdE: covar_par[2:4] = update_parameter_uni_2d_freq(covar_par_A[2:4], d=scale_proposal_divde, f=0.5, m = m_e, M = M_e)
				if do_varD: covar_parD = update_parameter_uni_2d_freq(covar_parD_A, d=0.1*scale_proposal_d, f=0.5, m = m_e, M = M_e)
				if do_varE: covar_parE = update_parameter_uni_2d_freq(covar_parE_A, d=0.1*scale_proposal_e, f=0.5, m = m_e, M = M_e)
		elif r[2] < .5 and (argstraitD != "" or argstraitE != "" or argscatD != "" or argscatE != ""): # update traits
			if argstraitD != "" and r[3] < .5:
				trait_parD = update_parameter_uni_2d_freq(trait_parD_A, d=0.1*scale_proposal_a_d, f=0.5, m = m_a_d, M = M_a_d)
			if argstraitE != "" and r[3] >= .5:
				trait_parE = update_parameter_uni_2d_freq(trait_parE_A, d=0.1*scale_proposal_a_e, f=0.5, m = m_a_e, M = M_a_e)
			if argscatD != "" and r[3] >= .5:
				cat_parD = update_parameter_uni_2d_freq(cat_parD_A, d=0.5, f=0.5, m = -3., M = 5.)
				cat_parD[catD_baseline] = 0.
			if argscatD != "" and r[3] < .5:
				hp_catD, hasting_catD = update_multiplier_proposal(hp_catD_A, d = 1.5)
			if argscatE != "" and r[3] < .5:
				cat_parE = update_parameter_uni_2d_freq(cat_parE_A, d=0.5, f=0.5, m = -3., M = 5.)
				cat_parE[catE_baseline] = 0.
			if argscatE != "" and r[3] >= .5:
				hp_catE, hasting_catE = update_multiplier_proposal(hp_catE_A, d = 1.5)
		else: # update dispersal rates
			if equal_d is True:
				d_temp, hasting_de = update_multiplier_proposal_freq(dis_rate_vec_A[:,0],d=1+.1*scale_proposal,f=update_rate_freq_d)
				dis_rate_vec = array([d_temp,d_temp]).T
			else:
				dis_rate_vec, hasting_de = update_multiplier_proposal_freq(dis_rate_vec_A,d=1+.1*scale_proposal,f=update_rate_freq_d)

	elif r[0] < update_freq[1]: # EXTINCTION RATES
		if args.TdE is False and r[1] < .5: 
			if args.lgE and r[2] < .5: # update logistic mid point
				x0_logisticE = update_parameter_uni_2d_freq(x0_logisticE_A,d=0.1*scale_proposal,f=0.5,m=-3,M=3)
			else:	
				if do_DivdD: covar_par[0:2] = update_parameter_uni_2d_freq(covar_par_A[0:2], d=scale_proposal_divdd, f=0.5, m = m_d, M = M_d)
				if do_DivdE or argsDdE: covar_par[2:4] = update_parameter_uni_2d_freq(covar_par_A[2:4], d=scale_proposal_divde, f=0.5, m = m_e, M = M_e)
				if do_varD: covar_parD = update_parameter_uni_2d_freq(covar_parD_A, d=0.1*scale_proposal_d, f=0.5, m = m_e, M = M_e)
				if do_varE: covar_parE = update_parameter_uni_2d_freq(covar_parE_A, d=0.1*scale_proposal_e, f=0.5, m = m_e, M = M_e)
		elif r[2] < .5 and (argstraitD != "" or argstraitE != "" or argscatD != "" or argscatE != ""): # update traits
			if argstraitD != "" and r[3] < .5:
				trait_parD = update_parameter_uni_2d_freq(trait_parD_A, d=0.1*scale_proposal_a_d, f=0.5, m = m_a_d, M = M_a_d)
			if argstraitE != "" and r[3] >= .5:
				trait_parE = update_parameter_uni_2d_freq(trait_parE_A, d=0.1*scale_proposal_a_e, f=0.5, m = m_a_e, M = M_a_e)
			if argscatD != "" and r[3] >= .5:
				cat_parD = update_parameter_uni_2d_freq(cat_parD_A, d=0.5, f=0.5, m = -3., M = 5.)
				cat_parD[catD_baseline] = 0.
			if argscatD != "" and r[3] < .5:
				hp_catD, hasting_catD = update_multiplier_proposal(hp_catD_A, d = 1.5)
			if argscatE != "" and r[3] < .5:
				cat_parE = update_parameter_uni_2d_freq(cat_parE_A, d=0.5, f=0.5, m = -3., M = 5.)
				cat_parE[catE_baseline] = 0.
			if argscatE != "" and r[3] >= .5:
				hp_catE, hasting_catE = update_multiplier_proposal(hp_catE_A, d = 1.5)
		else: # update extinction rates
			if equal_e is True:
				e_temp, hasting_de = update_multiplier_proposal_freq(ext_rate_vec_A[:,0],d=1+.1*scale_proposal,f=update_rate_freq_e)
				ext_rate_vec = array([e_temp,e_temp]).T
			else:
				ext_rate_vec, hasting_de = update_multiplier_proposal_freq(ext_rate_vec_A,d=1+.1*scale_proposal,f=update_rate_freq_e)

	elif r[0] <=update_freq[2]: # SAMPLING RATES
		r_vec=update_parameter_uni_2d_freq(r_vec_A,d=0.1*scale_proposal,f=update_rate_freq_r)
		if argsG is True and r[1] < .5:
			alpha, hasting_alpha = update_multiplier_proposal(alphaA,d=1.1)
		r_vec[:,0]=0
		#--> CONSTANT Q IN AREA 2
		if const_q ==1: r_vec[:,1] = r_vec[1,1]
		#--> CONSTANT Q IN AREA 2
		if const_q ==2: r_vec[:,2] = r_vec[1,2]
		#--> SYMMETRIC SAMPLING
		if equal_q is True: r_vec[:,2] = r_vec[:,1]
		r_vec[:,3]=1
		
		# CHECK THIS: CHANGE TO VALUE CLOSE TO 1? i.e. for 'ghost' area 
		if data_in_area == 1: r_vec[:,2] = small_number 
		elif data_in_area == 2: r_vec[:,1] = small_number
	elif it>0:
		gibbs_sample = 1
		d12_for_prior = dis_rate_vec[0:d12_prior_idx, 0].flatten()
		d21_for_prior = dis_rate_vec[0:d21_prior_idx, 1].flatten()
		if equal_d:
			d21_for_prior = np.array([])
		e1_for_prior = dis_rate_vec[0:e1_prior_idx, 0].flatten()
		e2_for_prior = dis_rate_vec[0:e2_prior_idx, 1].flatten()
		if equal_e:
			e2_for_prior = np.array([])
		prior_exp_rate = gibbs_sampler_hp(np.concatenate((d12_for_prior, d21_for_prior, e1_for_prior, e2_for_prior)), hp_alpha, hp_beta)
	
	# enforce constraints if any
	if len(constraints_covar)>0:
		covar_par[constraints_covar[constraints_covar<4]] = 0
		x0_logistic[constraints_covar[constraints_covar<4]] = 0
		dis_rate_vec[:,constraints_covar[constraints_covar<2]] = dis_rate_vec[0,constraints_covar[constraints_covar<2]]
		ext_rate_vec[:,constraints_covar[np.logical_and(constraints_covar >= 2, constraints_covar < 4)]-2] = ext_rate_vec[0,constraints_covar[np.logical_and(constraints_covar >= 2, constraints_covar < 4)]-2]
#	if len(args.symCov)>0:
#		args_symCov = np.array(args.symCov)
#		covar_par[args_symCov] = covar_par[args_symCov-1] 
#		x0_logistic[args_symCov] = x0_logistic[args_symCov-1] 
	if do_symCovD:
		covar_parD = covar_parD[idx2_symCovD][idx_symCovD]
		x0_logisticD = x0_logisticD[idx2_symCovD][idx_symCovD]
		covar_par[1] = covar_par[0]
	if do_symCovE:
		covar_parE = covar_parE[idx2_symCovE][idx_symCovE]
		x0_logisticE = x0_logisticE[idx2_symCovE][idx_symCovE]
		covar_par[3] = covar_par[2]
	
	## CHANGE HERE TO FIRST OPTIMIZE DISPERSAL AND THEN EXTINCTION
	if args.DdE and it < 100 and args.A != 3:
		covar_par[2:4]=0
	
	#x0_logistic = np.array([0,0,5,5])
	### GET LIST OF Q MATRICES ###
	if args.TdD: # time dependent D
#		covar_par[0:2]=0
#		x0_logistic[0:2]=0
		dis_vec = dis_rate_vec[Q_index,:]
		dis_vec = dis_vec[0:-1]
		transf_d=0
		time_var_d1,time_var_d2=time_varD,time_varD
	elif do_DivdD: # Diversity dependent D
		transf_d=4
		dis_vec = dis_rate_vec
		do_approx_div_traj = 1
	else: # temp dependent D
		transf_d=1
		dis_vec = dis_rate_vec
		time_var_d1,time_var_d2=time_varD,time_varD

	if args.lgD: transf_d = 2
	
	if data_in_area == 1:
		covar_par[[0,3]] = 0
		x0_logistic[[0,3]] = 0
	elif data_in_area == 2:
		covar_par[[1,2]] = 0
		x0_logistic[[1,2]] = 0
	

	if args.DisdE or model_DUO:
		marginal_dispersal_rate_temp = get_dispersal_rate_through_time(dis_vec,time_var_d1,time_var_d2,covar_par,x0_logistic,transf_d)
		numD12,numD21 =  get_num_dispersals(marginal_dispersal_rate_temp,r_vec)
		rateD12,rateD21 = marginal_dispersal_rate_temp[:,0], marginal_dispersal_rate_temp[:,1]

	if args.DdE: # Dispersal dep Extinction
		do_approx_div_traj = 1
		# What to do with the rest in here?
		#numD12res = rescale_vec_to_range(log(1+numD12), r=10., m=0)
		#numD21res = rescale_vec_to_range(log(1+numD21), r=10., m=0)
		#div_traj1,div_traj2 = get_est_div_traj(r_vec)
		
		#numD12res = rescale_vec_to_range((1+numD12)/(1+div_traj2), r=10., m=0)
		#numD21res = rescale_vec_to_range((1+numD21)/(1+div_traj1), r=10., m=0)

 		
		
		# NOTE THAT no. dispersals from 1=>2 affects extinction in 2 and vice versa
		transf_e=3
		#time_var_e2,time_var_e1 = numD12res, numD21res
		ext_vec = ext_rate_vec
	elif args.DisdE: # Dispersal RATE dep Extinction
		rateD12res = log(rateD12)
		rateD21res = log(rateD21)
		transf_e=1
		time_var_e2,time_var_e1 = rateD12res,rateD21res
		ext_vec = ext_rate_vec
	elif do_DivdE: # Diversity dep Extinction
		# NOTE THAT extinction in 1 depends diversity in 1
		transf_e=4
		#time_var_e1,time_var_e2 = get_est_div_traj(r_vec)
		do_approx_div_traj = 1
		ext_vec = ext_rate_vec
	elif args.TdE: # Time dep Extinction
#		covar_par[2:4]=0
#		x0_logistic[2:4]=0
		ext_vec = ext_rate_vec[Q_index,:]
		ext_vec = ext_vec[0:-1]
		transf_e=0
		time_var_e1,time_var_e2=time_varD,time_varD
	else: # Temp dependent Extinction
		ext_vec = ext_rate_vec
		transf_e=1
		time_var_e1,time_var_e2=time_varE,time_varE
	

	if (it % sampling_freq == 0 or args.A == 3):
		do_approx_div_traj = 1
	if do_approx_div_traj == 1:
		approx_d1,approx_d2,numD21,numD12,pres = approx_div_traj(nTaxa, dis_vec, ext_vec,
									do_DivdD, do_DivdE, do_varD, do_varE, argsDdE, argsG,
									r_vec, alpha, YangGammaQuant, pp_gamma_ncat, bin_size, Q_index, Q_index_first_occ,
									covar_par, covar_parD, covar_parE, offset_dis_div1, offset_dis_div2, offset_ext_div1, offset_ext_div2,
									time_series, len_time_series, bin_first_occ, first_area, time_varD, time_varE, data_temp,
									trait_parD, traitD, trait_parE, traitE,
									cat_parD, catD, cat_parE, catE, argstraitD, argstraitE, argscatD, argscatE)
		if do_DivdD:
			time_var_d2 = approx_d1 # Limits dispersal into 1
			time_var_d1 = approx_d2 # Limits dispersal into 2
		if do_DivdE:
			time_var_e1 = approx_d1
			time_var_e2 = approx_d2
		if args.DdE:
			time_var_e2 = numD12
			time_var_e1 = numD21
		
	if args.lgE: transf_e = 2
	if args.linE: transf_e = 3

	if model_DUO:
		numD12res = rescale_vec_to_range(log(1+numD12), r=10., m=0)
		numD21res = rescale_vec_to_range(log(1+numD21), r=10., m=0)
		# NOTE THAT no. dispersals from 1=>2 affects extinction in 2 and vice versa
		time_var_e2two, time_var_e1two=  numD12res, numD21res
		ext_vec = ext_rate_vec
		# LINEAR
		#_ Q_list, marginal_rates_temp= make_Q_Covar4VDdEDOUBLE(dis_vec,ext_vec,time_var_d1,time_var_d2,time_var_e1,time_var_e2,time_var_e1two,time_var_e2two,covar_par,x0_logistic,transf_d,transf_e=3)
		# EXPON
		if r[0] < update_freq[1] or it==0:
			Q_list, marginal_rates_temp= make_Q_Covar4VDdEDOUBLE(dis_vec,ext_vec,time_var_d1,time_var_d2,time_var_e1,time_var_e2,time_var_e1two,time_var_e2two,covar_par,x0_logistic,transf_d,transf_e=1)
	else:
		#print "dis_vec", dis_vec
		#print "ext_vec", ext_vec
		#print "time_var_d1", time_var_d1
		#print "time_var_d2", time_var_d2
		#print "time_var_e1",
		#print "time_var_e2",
		#print "covar_par", covar_par
		#print "x0_logistic", x0_logistic
		#print "transf_d", transf_d
		#print "transf_e", transf_e
		if r[0] < update_freq[1] or it==0:
			Q_list, marginal_rates_temp= make_Q_Covar4VDdE(dis_vec,ext_vec,time_var_d1,time_var_d2,time_var_e1,time_var_e2,covar_par, covar_parD, covar_parE, x0_logisticD, x0_logisticE,transf_d,transf_e, offset_dis_div1, offset_dis_div2, offset_ext_div1, offset_ext_div2)
	
		
	
	#__      
	#__      
	#__      
	#__      else:
	#__      		time_var_e1,time_var_e2 = get_est_div_traj(r_vec) # diversity dependent extinction
	#__      		Q_list= make_Q_Covar4VDdE(dis_vec[0:-1],ext_rate_vec,time_varD,time_var_e1,time_var_e2,covar_par,transf_d=0)	
	#__      	
	#__      	
	#__      elif args.DdE:
	#__      	# TRANSFORM Q MATRIX DeE MODEL	
	#__      	# NOTE THAT no. dispersals from 1=>2 affects extinction in 2 and vice versa
 	#__      	time_var_e2,time_var_e1 = get_num_dispersals(dis_rate_vec,r_vec)
	#__      	#print time_var_e1,time_var_e2
	#__      	Q_list= make_Q_Covar4VDdE(dis_rate_vec,ext_rate_vec,time_varD,time_var_e1,time_var_e2,covar_par)
	#__      	#for i in [1,10,20]:
	#__      	#	print Q_list[i]
	#__      	#quit()
	#__      elif args.DivdE:
	#__      	# TRANSFORM Q MATRIX DeE MODEL	
	#__      	# NOTE THAT extinction in 1 depends diversity in 1
 	#__      	time_var_e1,time_var_e2 = get_est_div_traj(r_vec)
	#__      	#print time_var_e1,time_var_e2
	#__      	Q_list= make_Q_Covar4VDdE(dis_rate_vec,ext_rate_vec,time_varD,time_var_e1,time_var_e2,covar_par)
	#__      else:
	#__      	# TRANSFORM Q MATRIX	
	#__      	Q_list= make_Q_Covar4V(dis_rate_vec,ext_rate_vec,time_varD,covar_par)
	#__      	#print "Q2", Q_list[0], covar_par
	#__      	#print Q_list[3]
	
	
	#if it % print_freq == 0: 
	#	print it,  Q_list[0],Q_list_old,covar_par
	#if r[0] < update_freq[1] or it==0:
	#			w_list,vl_list,vl_inv_list = get_eigen_list(Q_list)
	lik, weight_per_taxon = lik_DES(dis_vec, ext_vec, r_vec,
					time_var_d1, time_var_d2, time_var_e1, time_var_e2,
					covar_par, covar_parD, covar_parE, x0_logisticD, x0_logisticE, transf_d, transf_e,
					offset_dis_div1, offset_dis_div2, offset_ext_div1, offset_ext_div2,
					rho_at_present_LIST, r_vec_indexes_LIST, sign_list_LIST,OrigTimeIndex,
					Q_index, alpha, YangGammaQuant, pp_gamma_ncat, num_processes, use_Pade_approx, bin_last_occ,
					traits, trait_parD, traitD, trait_parE, traitE, cat, cat_parD, catD, catE, cat_parE)

	d12_for_prior = dis_rate_vec[0:d12_prior_idx, 0].flatten()
	d21_for_prior = dis_rate_vec[0:d21_prior_idx, 1].flatten()
	if equal_d:
		d21_for_prior = np.array([])
	d_prior = np.concatenate((d12_for_prior, d21_for_prior))
	e1_for_prior = dis_rate_vec[0:e1_prior_idx, 0].flatten()
	e2_for_prior = dis_rate_vec[0:e2_prior_idx, 1].flatten()
	if equal_e:
		e2_for_prior = np.array([])
	e_prior = np.concatenate((e1_for_prior, e2_for_prior))
	prior = prior_exp(d_prior, prior_exp_rate) + prior_exp(e_prior, prior_exp_rate)
	
	if args.hp:
		G_hp_alpha,G_hp_beta=1.,.1
		g_shape=G_hp_alpha + 2.#len(covar_par)/2.
		g_rate=G_hp_beta + np.sum((covar_par-0)**2)/2.
		hypGA = 1./np.random.gamma(shape= g_shape, scale= 1./g_rate)
		if hypGA>0: # use normal prior on covar par
			prior += prior_normal(covar_par,scale=sqrt(hypGA))
		else: # use uniform prior on covar par
			if np.anp.max(abs(covar_par)) > -hypGA:
				prior += -np.inf
			else:
				prior += 0
		g_shape=G_hp_alpha + 1.
		trait_par = np.concatenate((trait_parD, trait_parE))
		g_rate=G_hp_beta + np.sum((trait_par-0)**2)/2.
		hypGA = 1./np.random.gamma(shape= g_shape, scale= 1./g_rate)
		if hypGA>0: # use normal prior on trait par
			prior += prior_normal(trait_par,scale=sqrt(hypGA))
		else: # use uniform prior on trait par
			if np.anp.max(abs(trait_par)) > -hypGA:
				prior += -np.inf
			else:
				prior += 0
		cat_par_concat = np.concatenate((cat_parD, cat_parE))
		g_shape=G_hp_alpha + len(cat_par_concat)/2.
		g_rate=G_hp_beta + np.sum((cat_par_concat-1.)**2)/2.
		hypGA = 1./np.random.gamma(shape= g_shape, scale= 1./g_rate)
		if hypGA>0: # use normal prior on trait par
			prior += prior_normal(cat_par_concat,scale=sqrt(hypGA))
		else: # use uniform prior on trait par
			if np.anp.max(abs(cat_par_concat)) > -hypGA:
				prior += -np.inf
			else:
				prior += 0
	else:
		if do_DivdD: prior += prior_beta(1./covar_par[0:2][idx2_symCovD], 1., nTaxa/3.)
		if do_DivdE: prior += prior_beta(1./covar_par[2:4][idx2_symCovE], 1., nTaxa/3.)
		if argsDdE: prior += prior_normal(covar_par[2:4][idx2_symCovE], 0, 1)
		if do_varD: prior += prior_normal(covar_parD[idx2_symCovD], 0, 1)
		if do_varE: prior += prior_normal(covar_parE[idx2_symCovE], 0, 1)
		if args.lgD: prior += prior_normal(x0_logisticD[idx2_symCovD], 0, 1)
		if args.lgE: prior += prior_normal(x0_logisticE[idx2_symCovE], 0, 1)
		if argstraitD != "": prior += prior_normal(trait_parD, 0, 1)
		if argstraitE != "": prior += prior_normal(trait_parE, 0, 1)
		if argscatD != "":
			prior += prior_normal(cat_parD[catD_not_baseline], 0, hp_catD)
			prior += prior_exp(hp_catD, 1.)
		if argscatE != "":
			prior += prior_normal(cat_parE[catE_not_baseline], 0, hp_catE)
			prior += prior_exp(hp_catE, 1.)


	lik_alter = lik * scal_fac_TI[scal_fac_ind]
	hasting = hasting_de + hasting_alpha + hasting_catD + hasting_catE

	accepted_state = 0
	if args.A == 3:
		accepted_state = 1
		lik = minf
	if np.isfinite((lik_alter+prior+hasting)) == True:
		if it==0: 
			likA=lik_alter+0.
			MLik=likA-1
			ml_it=0
		if runMCMC == 1:
			# MCMC
			if (lik_alter-(likA* scal_fac_TI[scal_fac_ind]) + prior-priorA +hasting >= log(np.random.uniform(0,1))) or (gibbs_sample == 1):
				accepted_state=1
		else:
			# ML (approx maximum a posteriori algorithm)
			if ml_it==0: rr = 0 # only accept improvements
			else: rr = log(np.random.uniform(0,1))
			if (lik_alter-(likA* scal_fac_TI[scal_fac_ind]))*map_power >= rr:
				accepted_state=1
	elif it==0: 
		MLik=likA-1
	if accepted_state:
		dis_rate_vec_A= dis_rate_vec
		ext_rate_vec_A= ext_rate_vec
		r_vec_A=        r_vec
		likA=lik
		priorA = prior
		covar_par_A = covar_par
		covar_parD_A = covar_parD
		covar_parE_A = covar_parE
		trait_parD_A = trait_parD
		trait_parE_A = trait_parE
		cat_parD_A = cat_parD
		cat_parE_A = cat_parE
		hp_catD_A = hp_catD
		x0_logisticD_A = x0_logisticD
		x0_logisticE_A = x0_logisticE
		marginal_rates_A = marginal_rates_temp
		numD12A,numD21A = numD12,numD21
		alphaA = alpha
	
	log_to_file=0
	dis_rate_not_transformed = True
	ext_rate_not_transformed = True
	if it % print_freq == 0:
		sampling_prob = r_vec_A[:,1:len(r_vec_A[0])-1].flatten()
		q_rates = -log(sampling_prob)/bin_size
		print(it,"\t",likA,lik,scal_fac_TI[scal_fac_ind])
		if do_DivdD:
			dis_rate_vec_A[0,:] = dis_rate_vec_A[0,:] / (1. - ([offset_dis_div2, offset_dis_div1]/covar_par[0:2]))
		if do_DivdE:
			ext_rate_vec_A[0,:] = ext_rate_vec_A[0,:] * (1. - ([offset_ext_div2, offset_ext_div1]/covar_par[2:4]))
			ext_rate_not_transformed = False
		if args.lgD:
			print("covar_mean_dis:", covar_mean_dis)
			dis_rate_vec_A[0,:] = dis_rate_vec_A[0,:] * ( 1. + exp(-covar_parD_A * (covar_mean_dis - x0_logisticD_A)))
			dis_rate_not_transformed = False
		if args.lgE:
			ext_rate_vec_A[0,:] = ext_rate_vec_A[0,:] * ( 1. + exp(-covar_parE_A * (covar_mean_ext - x0_logisticE_A)))
			ext_rate_not_transformed = False
		print("\td:", dis_rate_vec_A.flatten(), "e:", ext_rate_vec_A.flatten(),"q:",q_rates,"alpha:",alphaA)
		print("\ta/K:",covar_par_A,"x0:",x0_logistic_A)
		print("\ta dispersal:", covar_parD_A)
		print("\ta extinction:", covar_parE_A)
		print("\tcont trait dispersal:", trait_parD_A)
		print("\tcont trait extinction:", trait_parE_A)
		print("\tcat dispersal:", np.exp(cat_parD_A))
		print("\tcat extinction:", np.exp(cat_parE_A))
	if it % sampling_freq == 0 and it >= burnin and runMCMC == 1:
		log_to_file=1
		# sampling_prob = r_vec_A[:,1:len(r_vec_A[0])-1].flatten()
		# q_rates = -log(sampling_prob)/bin_size
		# log_state= [it,likA+priorA, priorA,likA]+list(dis_rate_vec_A.flatten())+list(ext_rate_vec_A.flatten())+list(q_rates)
		# log_state = log_state+list(covar_par_A[0:2])	
		# if args.lgD: log_state = log_state+list(x0_logistic_A[0:2])
		# log_state = log_state+list(covar_par_A[2:4])	
		# if args.lgE: log_state = log_state+list(x0_logistic_A[2:4])
		# log_state = log_state+[prior_exp_rate]+[scal_fac_TI[scal_fac_ind]]
		# wlog.writerow(log_state)
		# logfile.flush()
		# os.fsync(logfile)
	if runMCMC == 0:
		if likA>MLik: 
			log_to_file=1
			# sampling_prob = r_vec_A[:,1:len(r_vec_A[0])-1].flatten()
			# q_rates = -log(sampling_prob)/bin_size
			# log_state= [it,likA+priorA, priorA,likA]+list(dis_rate_vec_A.flatten())+list(ext_rate_vec_A.flatten())+list(q_rates)
			# log_state = log_state+list(covar_par_A[0:2])	
			# if args.lgD: log_state = log_state+list(x0_logistic_A[0:2])
			# log_state = log_state+list(covar_par_A[2:4])	
			# if args.lgE: log_state = log_state+list(x0_logistic_A[2:4])
			# log_state = log_state+[prior_exp_rate]+[scal_fac_TI[scal_fac_ind]]
			# wlog.writerow(log_state)
			# logfile.flush()
			# os.fsync(logfile)
			MLik=likA+0.
			ML_dis_rate_vec = dis_rate_vec_A+0.
			ML_ext_rate_vec = ext_rate_vec_A+0.
			ML_covar_par    = covar_par_A   +0.
			ML_r_vec        = r_vec_A       +0.
			ML_alpha        = alphaA        +0.
			ml_it=0
		else:	ml_it +=1
		# exit when ML convergence reached
		if ml_it==100:
			print("restore ML estimates", MLik, likA+0.)
			dis_rate_vec_A = ML_dis_rate_vec
			ext_rate_vec_A = ML_ext_rate_vec
			covar_par_A    = ML_covar_par   
			r_vec_A        = ML_r_vec   
			alphaA         = ML_alpha    
			#if ml_it==100:
			print(scale_proposal, "changed to:",)
			scale_proposal = 0.1
			print(scale_proposal)
			#update_rate_freq = 0.15
		#	if ml_it==200:
		#		print scale_proposal, "changed to:",
		#		scale_proposal = 0.5
		#if ml_it>8:
		#	scale_proposal = 0 
		#	print lik, likA, MLik
		if ml_it>max_ML_iterations:
			msg= "Convergence reached. ML = %s (%s iterations)" % (round(MLik,3),it)
			sys.exit(msg)
	if log_to_file:
		sampling_prob = r_vec_A[:,1:len(r_vec_A[0])-1].flatten()
		q_rates = -log(sampling_prob)/bin_size
		if do_DivdD and dis_rate_not_transformed:
			dis_rate_vec_A[0,:] = dis_rate_vec_A[0,:] / (1. - ([offset_dis_div2, offset_dis_div1]/covar_par[0:2]))
		if do_DivdE and ext_rate_not_transformed:
			ext_rate_vec_A[0,:] = ext_rate_vec_A[0,:] * (1. - ([offset_ext_div2, offset_ext_div1]/covar_par[2:4]))
		if args.lgD and dis_rate_not_transformed:
			dis_rate_vec_A[0,:] = dis_rate_vec_A[0,:] * ( 1. + exp(-covar_parD_A * (covar_mean_dis - x0_logisticD_A)))
		if args.lgE and ext_rate_not_transformed:
			ext_rate_vec_A[0,:] = ext_rate_vec_A[0,:] * ( 1. + exp(-covar_parE_A * (covar_mean_ext - x0_logisticE_A)))
		log_dis_rate = dis_rate_vec_A.flatten()
		log_ext_rate = ext_rate_vec_A.flatten()
		log_state= [it,likA+priorA, priorA,likA]+list(log_dis_rate)+list(log_ext_rate)+list(q_rates)
		if do_varD: log_state = log_state+list(covar_parD_A)
		if args.lgD: log_state = log_state+list(x0_logisticD_A + mean_varD_before_centering)
		if do_DivdD: log_state = log_state+list(covar_par_A[0:2])
		if do_varE: log_state = log_state+list(covar_parE_A)
		if args.lgE: log_state = log_state+list(x0_logisticE_A + mean_varE_before_centering)
		if do_DivdE: log_state = log_state+list(covar_par_A[2:4])
		if argsDdE: log_state = log_state+list(covar_par_A[2:4])
		if argsG: log_state = log_state + list(alpha)
		if do_DivdD or do_DivdE:
			if data_in_area == 1:
				idx_dis = 1
				idx_ext = 0
				idx_k_d = 1
				idx_k_e = 2
				covar_par_equil = covar_par[2] # For disp dep ext
			if data_in_area == 2:
				idx_dis = 0
				idx_ext = 1
				idx_k_d = 0
				idx_k_e = 3
				covar_par_equil = covar_par[3] # For disp dep ext
			for i in range(slices_dis):
				for y in range(slices_ext):
					if data_in_area == 0:
						dis = dis_rate_vec_A[i,:]
						ext = ext_rate_vec_A[y,:]
						if do_DivdD:
							k_d = covar_par[0:2]
						else:
							k_d = np.array([np.inf, np.inf])
						if do_DivdE:
							k_e = covar_par[2:4]
						else:
							k_e = np.array([np.inf, np.inf]) # np.array([0., 0.]) #
						x_init = [np.min([k_d[0],k_e[0]])* 0.99, np.min([k_d[1],k_e[1]])* 0.99, 0.]
						opt_div = minimize(calc_diff_equil_two_areas, x_init, method = 'nelder-mead')
						carrying_capacity = np.array([opt_div.x[0] + opt_div.x[2], opt_div.x[1] + opt_div.x[2]])
					else:
						dis = dis_rate_vec_A[i,idx_dis]
						ext = ext_rate_vec_A[y,idx_ext]
						if do_DivdD:
							k_d = covar_par[idx_k_d]
						else:
							k_d = np.inf
						if do_DivdE:
							k_e = covar_par[idx_k_e]
						else:
							k_e = np.inf
						x_init = [np.min([k_d,k_e])* 0.99, 0.]
						opt_div = minimize(calc_diff_equil_one_area, x_init, method = 'nelder-mead')
						carrying_capacity = np.array([opt_div.x[0] + opt_div.x[1]])
					log_state = log_state + list(carrying_capacity)
		log_state = log_state + list(trait_parD_A) + list(trait_parE_A)
		if argscatD != "":
			#log_dis_rate = np.repeat(log_dis_rate, len(unique_catD)) * np.tile(cat_parD, len(log_dis_rate))
			log_state = log_state + list(np.exp(cat_parD)) + list(hp_catD)
		if argscatE != "":
			#log_ext_rate = np.repeat(log_ext_rate, len(unique_catE)) * np.tile(cat_parE, len(log_ext_rate))
			log_state = log_state + list(np.exp(cat_parE)) + list(hp_catE)
		log_state = log_state+[prior_exp_rate]+[scal_fac_TI[scal_fac_ind]]
		wlog.writerow(log_state)
		logfile.flush()


	log_marginal_rates = 1
	log_n_dispersals = 0
	if log_marginal_rates and log_to_file == 1:
		temp_marginal_d12 = list(marginal_rates_A[0][:,0][::-1])
		temp_marginal_d21 = list(marginal_rates_A[0][:,1][::-1])
		temp_marginal_e1  = list(marginal_rates_A[1][:,0][::-1])
		temp_marginal_e2  = list(marginal_rates_A[1][:,1][::-1])
		if traits or cat:
			marginal_disrate = get_marginal_traitrate(marginal_rates_A[0], nTaxa, pres, traits, traitD, trait_parD_A, cat, catD, cat_parD_A)
			temp_marginal_d12 = list(marginal_disrate[0,:])
			temp_marginal_d21 = list(marginal_disrate[1,:])
			marginal_extrate = get_marginal_traitrate(marginal_rates_A[1], nTaxa, pres, traits, traitE, trait_parE_A, cat, catE, cat_parE_A)
			temp_marginal_e1 = list(marginal_extrate[0,:])
			temp_marginal_e2 = list(marginal_extrate[1,:])
		log_state = [it]+temp_marginal_d12+temp_marginal_d21+temp_marginal_e1+temp_marginal_e2
		rlog.writerow(log_state)
		ratesfile.flush()
		os.fsync(ratesfile)
		# Log predicted presence - only works for ML
		if args.log_distr:
			pres_file ="%s/%s_%s%s%s%s%s%s.log" % (output_wd,name_file,simulation_no,Q_times_str,ti_tag,model_tag,args.out,"_distr")
			pres = np.transpose(pres)
			np.savetxt(pres_file, pres, delimiter="\t")
		# Log weights for sampling heterogeneity - only works for ML
		if args.log_weights:
			weight_file ="%s/%s_%s%s%s%s%s%s.log" % (output_wd,name_file,simulation_no,Q_times_str,ti_tag,model_tag,args.out,"_weight")
			weight_per_taxon =  np.transpose(weight_per_taxon)
			np.savetxt(weight_file, weight_per_taxon, delimiter="\t")
	if args.log_div and log_to_file == 1:
		log_state = [it] + list(approx_d1[::-1]) + list(approx_d2[::-1])
		divlog.writerow(log_state)
		divfile.flush()
		os.fsync(divfile)
	if args.log_dis and log_to_file == 1:
		log_state = [it] + list(numD12[::-1]) + list(numD21[::-1])
		dislog.writerow(log_state)
		disfile.flush()
		os.fsync(disfile)


print("elapsed time:", time.time()-start_time)

if num_processes>0:
	pool_lik.close()
	pool_lik.join()


quit()

