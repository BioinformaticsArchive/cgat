import os
import re
import sys
import collections

import CGAT.Experiment as E
import CGAT.Pipeline as P
import CGAT.IOTools as IOTools
import CGAT.Expression as Expression
import CGAT.Bed as Bed

#########################################################################
#########################################################################
#########################################################################
def countReadsWithinWindows( bedfile, windowfile, outfile, counting_method = "midpoint" ):
    '''count reads in *bedfile* within *windowfile*.

    '''
    to_cluster = True

    job_options = "-l mem_free=4G"

    if counting_method == "midpoint":
        f = '''| awk '{a = $2+($3-$2)/2; printf("%s\\t%i\\t%i\\n", $1, a, a+1)}' '''
    elif countig_method == "nucleotide":
        f = ""
    else: 
        raise ValueError("unknown counting method: %s" % counting_method )

    statement = '''
    zcat %(bedfile)s
    %(f)s
    | coverageBed -a stdin -b %(windowfile)s -split
    | sort -k1,1 -k2,2n 
    | gzip
    > %(outfile)s
    '''

    P.run()

#########################################################################
#########################################################################
#########################################################################
def aggregateWindowsReadCounts( infiles, outfile ):
    '''aggregate tag counts for each window.

    coverageBed outputs the following columns:
    1) Contig
    2) Start
    3) Stop
    4) Name
    5) The number of features in A that overlapped (by at least one base pair) the B interval.
    6) The number of bases in B that had non-zero coverage from features in A.
    7) The length of the entry in B.
    8) The fraction of bases in B that had non-zero coverage from features in A.

    For bed: use column 5
    For bed6: use column 7
    For bed12: use column 13

    Tiles with no counts will not be output.
    '''
    
    to_cluster = True

    # get bed format
    bed_columns = Bed.getNumColumns( infiles[0] )
    # +1 as awk is 1-based
    column = bed_columns - 4 + 1

    src = " ".join( [ '''<( zcat %s | awk '{printf("%%s:%%i-%%i\\t%%i\\n", $1,$2,$3,$%s );}' ) ''' % (x,column) for x in infiles] )
    tmpfile = P.getTempFilename( "." )
    statement = '''paste %(src)s > %(tmpfile)s'''
    P.run()
    
    tracks = [ re.sub( "\..*", '', os.path.basename(x) ) for x in infiles ]

    outf = IOTools.openFile( outfile, "w")
    outf.write( "interval_id\t%s\n" % "\t".join( tracks ) )
    
    for line in open( tmpfile, "r" ):
        data = line[:-1].split("\t")
        genes = list(set([ data[x] for x in range(0,len(data), 2 ) ]))
        values = [ int(data[x]) for x in range(1,len(data), 2 ) ]
        if sum(values) == 0: continue
        assert len(genes) == 1, "paste command failed, wrong number of genes per line: '%s'" % line
        outf.write( "%s\t%s\n" % (genes[0], "\t".join(map(str, values) ) ) )
    
    outf.close()

    os.unlink(tmpfile)


#########################################################################
#########################################################################
#########################################################################
def buildDMRStats( infile, outfile, method ):
    '''build dmr summary statistics.
    '''
    results = collections.defaultdict( lambda : collections.defaultdict(int) )

    status =  collections.defaultdict( lambda : collections.defaultdict(int) )
    x = 0
    for line in IOTools.iterate( IOTools.openFile( infile ) ):
        key = (line.treatment_name, line.control_name )
        r,s = results[key], status[key]
        r["tested"] += 1
        s[line.status] += 1

        is_significant = line.significant == "1"
        up = float(line.l2fold) > 0
        down = float(line.l2fold) < 0
        fold2up = float(line.l2fold) > 1
        fold2down = float(line.l2fold) < -1
        fold2 = fold2up or fold2down

        if up: r["up"] += 1
        if down: r["down"] += 1
        if fold2up: r["l2fold_up"] += 1
        if fold2down: r["l2fold_down"] += 1

        if is_significant:
            r["significant"] += 1
            if up: r["significant_up"] += 1
            if down: r["significant_down"] += 1
            if fold2: r["fold2"] += 1
            if fold2up: r["significant_l2fold_up"] += 1
            if fold2down: r["significant_l2fold_down"] += 1
            
    header1, header2 = set(), set()
    for r in results.values(): header1.update( r.keys() )
    for s in status.values(): header2.update( s.keys() )
    
    header = ["method", "treatment", "control" ]
    header1 = list(sorted(header1))
    header2 = list(sorted(header2))

    outf = IOTools.openFile( outfile, "w" )
    outf.write( "\t".join(header + header1 + header2) + "\n" )

    for treatment,control in results.keys():
        key = (treatment,control)
        r = results[key]
        s = status[key]
        outf.write( "%s\t%s\t%s\t" % (method,treatment, control))
        outf.write( "\t".join( [str(r[x]) for x in header1 ] ) + "\t" )
        outf.write( "\t".join( [str(s[x]) for x in header2 ] ) + "\n" )

def outputAllWindows( infile, outfile ):
    '''output all Windows as a bed file with the l2fold change
    as a score.
    '''
    outf = IOTools.openFile( outfile, "w" )
    for line in IOTools.iterate( IOTools.openFile( infile ) ):
        outf.write( "\t".join( (line.contig, line.start, line.end, "%6.4f" % float(line.l2fold ))) + "\n" ) 

    outf.close()

        # ###########################################
        # ###########################################
        # ###########################################
        # # plot length versus P-Value
        # data = Database.executewait( dbhandle, 
        #                              '''SELECT end - start, pvalue 
        #                      FROM %(tablename)s
        #                      WHERE significant'''% locals() ).fetchall()

        # # require at least 10 datapoints - otherwise smooth scatter fails
        # if len(data) > 10:
        #     data = zip(*data)

        #     pngfile = "%(outdir)s/%(tileset)s_%(design)s_%(method)s_pvalue_vs_length.png" % locals()
        #     R.png( pngfile )
        #     R.smoothScatter( R.log10( ro.FloatVector(data[0]) ),
        #                      R.log10( ro.FloatVector(data[1]) ),
        #                      xlab = 'log10( length )',
        #                      ylab = 'log10( pvalue )',
        #                      log="x", pch=20, cex=.1 )

        #     R['dev.off']()


def outputRegionsOfInterest( infiles, outfile, max_per_sample = 10, sum_per_group = 40 ):
    '''output windows according to various filters.

    The output is a mock analysis similar to a differential expression 
    result.
    '''
    job_options = "-l mem_free=64G"

    design_file, counts_file = infiles

    design = Expression.readDesignFile( design_file )
    
    # remove tracks not included in the design
    design = dict( [ (x,y) for x,y in design.items() if y.include ] )

    # define the two groups
    groups = sorted(set( [x.group for x in design.values() ] ))

    # build a filtering statement
    groupA, groupB = groups
    upper_levelA = "max( (%s) ) < %f" % ( \
        ",".join( \
            [ "int(r['%s'])" % x for x,y in design.items() if y.group == groupA ] ),
        max_per_sample )

    sum_levelA = "sum( (%s) ) > %f" % ( \
        ",".join( \
            [ "int(r['%s'])" % x for x,y in design.items() if y.group == groupB ] ),
        sum_per_group )

    upper_levelB = "max( (%s) ) < %f" % ( \
        ",".join( \
            [ "int(r['%s'])" % x for x,y in design.items() if y.group == groupB ] ),
        max_per_sample )

    sum_levelB = "sum( (%s) ) > %f" % ( \
        ",".join( \
            [ "int(r['%s'])" % x for x,y in design.items() if y.group == groupA ] ),
        sum_per_group )

    statement = '''
    zcat %(counts_file)s
    | python %(scriptsdir)s/csv_select.py 
            --log=%(outfile)s.log
            "(%(upper_levelA)s and %(sum_levelA)s) or (%(upper_levelB)s and %(sum_levelB)s)"
    | python %(scriptsdir)s/runExpression.py
            --log=%(outfile)s.log          
            --filename-design=%(design_file)s
            --filename-tags=-
            --method=mock
            --filter-min-counts-per-sample=0 
    | gzip 
    > %(outfile)s
    '''

    P.run()

#########################################################################
#########################################################################
#########################################################################
def runDE( infiles, outfile, outdir, method ):
    '''run DESeq or EdgeR.

    The job is split into smaller sections. The order of the input 
    data is randomized in order to avoid any biases due to chromosomes and
    break up local correlations.

    At the end, a new q-value is computed from all results.
    '''

    to_cluster = True
    
    design_file, counts_file = infiles

    prefix = os.path.basename( outfile )

    # the post-processing strips away the warning,
    # renames the qvalue column to old_qvalue
    # and adds a new qvalue column after recomputing
    # over all windows.
    statement = '''zcat %(counts_file)s 
              | perl %(scriptsdir)s/randomize_lines.pl -h
              | %(cmd-farm)s
                  --input-header 
                  --output-header 
                  --split-at-lines=200000 
                  --cluster-options="-l mem_free=8G"
                  --log=%(outfile)s.log
                  --output-pattern=%(outdir)s/%%s
                  --subdirs
              "python %(scriptsdir)s/runExpression.py
              --method=%(method)s
              --filename-tags=-
              --filename-design=%(design_file)s
              --output-filename-pattern=%%DIR%%/%(prefix)s_
              --deseq-fit-type=%(deseq_fit_type)s
              --deseq-dispersion-method=%(deseq_dispersion_method)s
              --deseq-sharing-mode=%(deseq_sharing_mode)s
              --filter-min-counts-per-row=%(tags_filter_min_counts_per_row)i
              --filter-min-counts-per-sample=%(tags_filter_min_counts_per_sample)i
              --filter-percentile-rowsums=%(tags_filter_percentile_rowsums)i
              --log=%(outfile)s.log
              --fdr=%(edger_fdr)f"
              | grep -v "warnings"
              | perl %(scriptsdir)s/regtail.pl ^test_id
              | perl -p -e "s/qvalue/old_qvalue/"
              | python %(scriptsdir)s/table2table.py 
              --log=%(outfile)s.log
              --method=fdr 
              --column=pvalue
              --fdr-method=BH
              --fdr-add-column=qvalue
              | gzip
              > %(outfile)s '''

    P.run()

