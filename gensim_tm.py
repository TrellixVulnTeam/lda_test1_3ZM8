import datetime
from xls_loader import get_cands_data
from xls_loader import get_translated_text
from infra import get_cand
from CandData import CandData
from gensim_lda import gensim_lda_run
from gensim_lda import gensim_load_model
from gensim_lda import gensim_apply_text_on_model
from gensim_lda import gensim_apply_text_on_model2
from gensim_lda import gensim_analyze_corpus
from gensim_lda import dump_data_lemmatized
from gensim_lda import get_data_lemmatized
from gensim_lda import text2corpus
from infra import convert_locations
from infra import fill_zeros
from xls_loader import is_empty_text
from keras_lda import keras_lda_run
import numpy as np

MAX_LINE = 12120
N = 15
YEARS = [2015]
NAMES = ["kkz0", "kkz1", "kkz2", "kkz3", "all"]
DUMP_LOCATIONS = False
DUMP_MY_MATCHES = True
TOPIC_WORDS = 100
id2matches = {}
index2cand = {}
sample1_index2cand = {}
sample2_index2cand = {}
G = "gensim"
K = "keras"



def dump_big5():
    f = open("big5.csv", "w")
    h = "B1,B2,B3,B4,B5,dapar,tzadak,mavdak1,mavdak2,rejected,nf,ne,socioT,socioP\n"
    f.write("{}".format(h))
    db = get_cands_data('thesis_db.xls', MAX_LINE)
    reviewed_cands = []
    c = 0

    for line in range(MAX_LINE):
        this_cand_id = db.ID_coded[line]
        if this_cand_id not in reviewed_cands:
            reviewed_cands.append(this_cand_id)
            if not is_empty_text(db.bts_a[line]):
                c = c + 1
                cand = CandData(db, line)

                if cand.notEntered:
                    ne = 1
                else:
                    ne = 0

                if cand.notFinished:
                    nf = 1
                else:
                    nf = 0
                s = "{},{},{},{},{},{},{},{},{},{},{},{},{},{}".format(db.bts_a[line], db.bts_c[line],
                                                  db.bts_e[line], db.bts_n[line],db.bts_o[line], cand.dapar, cand.tzadak,
                                                  cand.mavdak1, cand.mavdak2, cand.rejected, nf, ne,
                                                                 cand.socio_t, cand.socio_p)
                f.write("{}\n".format(s))
                print(s)

    print("sum {}".format(c))
    f.close()


def dump_applied_results(d_lists, i2c, name_suf):
    print(d_lists)
    header = "id,"
    for i in range(N):
        header = "{}t{},".format(header, i)
    header = "{}A10,A30,MAX,KKZ,KKZT,Officer,DAPAR,TZADAK,MAVDAK1,MAVDAK2,REJECTED,EXCEL,GRADE,SOCIO_TIRONUT,SOCIO_PIKUD".format(header)

    index = 0
    fname = "_gensim_applied_{}_{}_topics.csv".format(name_suf, N)
    f = open(fname, "w")
    f.write("{}\n".format(header))

    for key in i2c:
        cand = i2c[key]
        a10 = 0
        a30 = 0
        max = 0
        f.write("{},{},".format(cand.id, cand.year))
        #probabilities = model.get_document_topics(corpus[index], minimum_probability=0.00001)
        #prob_list = [prob[1] for prob in probabilities]
        prob_list = d_lists[index]
        locations = convert_locations(prob_list)
        for p in prob_list:
            if DUMP_LOCATIONS:
                f.write("{},".format(locations[index]))
            else:
                f.write("{:.5f},".format(p))
            if p >= 0.1:
                a10 = a10 + 1
            if p >= 0.3:
                a30 = a30 + 1
            if p > max:
                max = p

        if cand.otype == 0:
            kkz = 0
        else:
            kkz = 1
        f.write("{},{},{:.5f},{},{},{},{},{},{},{},{},{},{},{},{}\n".format(a10, a30, max, kkz, cand.otype, cand.officer,
                                                                      cand.dapar, cand.tzadak, cand.mavdak1,
                                                                      cand.mavdak2, cand.rejected, cand.excel,
                                                                      cand.grade, cand.socio_t, cand.socio_p))
        index = index + 1
    f.close()


def apply_new_text_on_train_model(train_model, new_text, i2c, name_suf):
    vectors = gensim_apply_text_on_model2(train_model, new_text[0])
    #dist_lists = []
    #for v in vectors:
    #    dist_lists.append(fill_zeros(v, N))
    #dump_applied_results(dist_lists, i2c, name_suf)


def load_lda(fname):
    model = gensim_load_model(fname)
    topicsf = open("_gensim_loaded_{}.txt".format(fname), "w")
    s = model.print_topics()
    for topic in s:
        topicsf.write("{}\n".format(topic))
    topicsf.close()


def create_word2prob_for_topic(topic_str):
    words = {}
    words_and_probs = topic_str[1].split(' + ')
    for item in words_and_probs:
        t = item.split('*')
        words[t[1].strip('"')] = float(t[0])

    return words, topic_str[0]


def create_word2prob_dicts(model):
    word2prob_dicts_list = [[]] * N
    s = model.print_topics(num_topics=N, num_words=TOPIC_WORDS)

    for topic in s:
        w2p, topic_i = create_word2prob_for_topic(topic)
        word2prob_dicts_list[topic_i] = w2p

    return word2prob_dicts_list


def calc_total_match(words, dict):
    match = 0
    match_str = ""

    for word in words:
        if word in dict:
            match = match + dict[word]
            match_str = "{} {}*{} ".format(match_str, word, dict[word])

    return match, match_str


def dump_cand_matches(cand, cand_words, word2prob, f, calc_f, topics_n, c_index, gensim_probs):
    cand_matches = []
    f.write("{}) Candidate {}:\n".format(c_index, cand.id))
    calc_f.write("{}) Candidate {}:\n".format(c_index, cand.id))

    prob_list = [prob[1] for prob in gensim_probs]
    locations = convert_locations(prob_list)

    i = 0
    for w2p in word2prob:
        p = gensim_probs[i]
        match, match_str = calc_total_match(cand_words, w2p)
        calc_f.write("{}) [{:.3f}] - {}\n".format(i, match, match_str))
        if i == 0:
            zero_match = match
        cand_matches.append(match)
        f.write("Topic {} : words matches = {:.3f}, engine_prob = {:.3f}, engine location = {}\n".format(i, match, p[1], locations[p[0]]))
        i = i + 1

    f.write("\n")
    zero_first = (zero_match == max(cand_matches))
    if zero_first and cand.sex == 1:
        print("{} - {}".format(cand.id, cand_words))
    return cand_matches, zero_first


def dump_matches(engine, model, corpus, texts, word2prob_list, otype, topics_n):
    lemmatized_text = get_data_lemmatized(texts)
    calc_f = open("_{}_match_calc_details.txt".format(engine), "w")
    fname = "_{}_cands_matches_{}_{}_topics".format(engine, NAMES[otype], topics_n)
    f = open(fname, "w")
    fzl = []
    mzl = []
    males = [0, 0, 0, 0]
    females = [0, 0, 0, 0]

    i = 0
    for key in index2cand:
        cand = index2cand[key]
        if otype == 4 or cand.otype == otype:
            if cand.id == 11847784:
                stop = True
            probabilities = get_probabilities(engine, model, i, corpus)
            print(cand.id)
            print(probabilities)
            cand_matches, zero_first = dump_cand_matches(cand, lemmatized_text[i], word2prob_list, f, calc_f, topics_n, i, probabilities)
            id2matches[cand.id] = cand_matches
            if zero_first:
                if cand.sex == 0:
                    fzl.append(cand.id)
                    females[cand.otype] = females[cand.otype] + 1
                else:
                    mzl.append(cand.id)
                    males[cand.otype] = males[cand.otype] + 1
            i = i + 1

    f_z = len(fzl)
    total_z = f_z + len(mzl)
    print("f%={} -  {}/{}".format(f_z/total_z, f_z, total_z))
    print(males)
    print(females)
    print(fzl)
    print(mzl)
    calc_f.close()
    f.close()


def get_probabilities(engine, model, doc_index, corpus=None):
    if engine == G:
        return model.get_document_topics(corpus[doc_index], minimum_probability=0.00001)
    else:
        return list((i, prob) for i, prob in enumerate(model.doc_topic_[doc_index]))


def dump_single_run_results(engine, model, corpus, otype, topics_n):
    header = "id,sex,year,"
    for i in range(topics_n):
        header = "{}t{},".format(header, i)
    header = "{}A10,A30,MAX,KKZ,KKZT,Officer,DAPAR,TZADAK,MAVDAK1,MAVDAK2,REJECTED,EXCEL,GRADE,SOCIO_TIRONUT,SOCIO_PIKUD".format(header)

    fname = "_{}_{}_{}_topics_dist.csv".format(engine, NAMES[otype], topics_n)
    f = open(fname, "w")
    f.write("{}\n".format(header))

    for i, key in enumerate(index2cand):
        cand = index2cand[key]
        if otype == 4 or cand.otype == otype:
            # NOTICE: Assumes dump_matches was already called before
            my_matches = id2matches[cand.id]
            a10 = 0
            a30 = 0
            max = 0
            f.write("{},{},{},".format(cand.id, cand.sex, cand.year))
            probabilities = get_probabilities(engine, model, i, corpus)
            #if engine == G:
            #    probabilities = get_gensim_probabilities(model, corpus, index)
            #else:
            #    probabilities = get_keras_probabilities(model, index)
            prob_list = [prob[1] for prob in probabilities]
            locations = convert_locations(prob_list)
            #locations = convert_locations(my_matches)
            p_index = 0
            for p in probabilities:
                if DUMP_LOCATIONS:
                    f.write("{},".format(locations[p[0]]))
                    #A hack to dump 1 if first and zero if not
                    #if locations[p[0]] == (topics_n - 1):
                    #    f.write("1,")
                    #else:
                    #    f.write("0,")
                else:
                    if DUMP_MY_MATCHES:
                        if p_index < len(my_matches):
                            f.write("{:.3f},".format(my_matches[p_index]))
                        else:
                            print("index {} not found in my_matches".format(p_index))
                    else:
                        f.write("{:.5f},".format(p[1]))
                p_index = p_index + 1

                if p[1] >= 0.1:
                    a10 = a10 + 1
                if p[1] >= 0.3:
                    a30 = a30 + 1
                if p[1] > max:
                    max = p[1]

            if cand.otype == 0:
                kkz = 0
            else:
                kkz = 1
            f.write("{},{},{:.5f},{},{},{},{},{},{},{},{},{},{},{},{}\n".format(a10, a30, max, kkz, cand.otype, cand.officer,
                                                                          cand.dapar, cand.tzadak, cand.mavdak1,
                                                                          cand.mavdak2, cand.rejected, cand.excel,
                                                                          cand.grade, cand.socio_t, cand.socio_p))
    f.close()


def run_gensim_engine(text, fname, topics_n):
    model, corp = gensim_lda_run(text, topics_n)
    topicsf = open(fname, "w")
    s = model.print_topics(num_topics=N, num_words=TOPIC_WORDS)
    for topic in s:
        topicsf.write("{}\n".format(topic))
    topicsf.close()
    word2prob_list = create_word2prob_dicts(model)
    return model, corp, word2prob_list


def run_keras_engine(text, fname, topics_n):
    word2prob_list = []

    id2word, corpus = text2corpus(text)
    model = keras_lda_run(corpus, id2word, topics_n)

    topicsf = open(fname, "w")
    topic_word = model.topic_word_  # model.components_ also works

    for i, topic_dist in enumerate(topic_word):
        d = {}
        topic_words = np.array(list(id2word.token2id.keys()))[np.argsort(topic_dist)][:-(TOPIC_WORDS + 1):-1]
        topic_str = '{}: '.format(i)
        for word in topic_words:
            prob = topic_dist[id2word.token2id[word]]
            d[word] = round(prob, 3)
            topic_str = "{}{:.3f}*{}, ".format(topic_str, prob, word)
        word2prob_list.append(d)
        topicsf.write(topic_str + '\n')
    topicsf.close()
    return model, corpus, word2prob_list


def run_lda(engine, text, otype, to_dump, topics_n=N):
    size = len(text)
    print("Valid Candidates ({}): {}".format(NAMES[otype], size))
    if size > 0:
        fname = "_{}_{}_{}_topics.txt".format(engine, NAMES[otype], topics_n)
        if engine == G:
            model, corpus, word2prob_list = run_gensim_engine(text, fname, topics_n)
        else:
            model, corpus, word2prob_list = run_keras_engine(text, fname, topics_n)
        dump_matches(engine, model, corpus, text, word2prob_list, otype, topics_n)
        if to_dump:
            dump_single_run_results(engine, model, corpus, otype, topics_n)
        return model
    else:
        return None


print(datetime.datetime.now())
full_text = get_translated_text("Translated_text.txt")
#full_text = get_translated_text("fake_translated.txt")
text = full_text[:MAX_LINE]
db = get_cands_data('thesis_db.xls', MAX_LINE)
#db = get_cands_data('fake_db.xls', MAX_LINE)
reviewed_cands = []
errors = [0, 0, 0, 0, 0, 0]
lda_text = [[], [], [], []]
accum_kkz_text = [""] * 4
accum_grade_text = [""] * 41
entire_text = []
sample1_text = []
sample2_text = []
boys = []
girls = []
# Accumulated train text is gathered by certain criteria (e.g grade) and every index in it is a value that accumulates
# text matching this value, There are no values higher than 100 for any criteria
accum_train_text = [""] * 100
accum_cands = 0
cand_ids = []

high = []
low = []

index = 0
for line in text:
    this_cand_id = db.ID_coded[index]
    if this_cand_id not in reviewed_cands:
        reviewed_cands.append(this_cand_id)
        cand = get_cand(db, full_text, index, YEARS, errors)
        if cand is not None:
            entire_text.append(line)
            cand_ids.append(cand.id)
            lda_text[cand.otype].append(line)
            index2cand[index] = cand
            #if cand.sex == 0:
            #    girls.append(line)
            #else:
            #    boys.append(line)

            #sample1_index = len(sample1_text)
            #sample2_index = len(sample2_text)
            #if (sample1_index < 100 and cand.otype == 0) or (sample2_index < 100 and cand.otype == 3):
            #if index > 89:
                # Cand goes to applied sample
                #if sample1_index < 100 and cand.otype == 0:
                #sample1_text.append(line)
                #sample1_index2cand[sample1_index] = cand
                #else:
                #    sample2_text.append(line)
                #    sample2_index2cand[sample2_index] = cand

            #else:
            #    # Cand goes to accumulate train text
            #    if cand.grade == 0:
            #        ii = 0
            #    else:
            #        ii = cand.grade - 59
            #    accum_train_text[ii] = accum_train_text[ii] + line
            #    accum_cands = accum_cands + 1


            #if cand.otype == 3 and not cand.grade == "" and int(cand.grade) > 83:
            #entire_text.append(line)

            #if cand.otype == 3 and not cand.grade == "" and int(cand.grade) < 80:
            #   low.append(line)
    index = index + 1

lem_text = get_data_lemmatized(entire_text)

#for i in range(4):
#    run_lda(lda_text[i], i, True, N)
#for topics in range(16, 26):
#run_gensim(lem_text, 4, True, N)
run_lda(K, lem_text, 4, True, N)
#run_keras(lem_text, 4, N)
#dump_data_lemmatized(entire_text, cand_ids, "_All_2015_lemmatized.txt")

#gensim_analyze_corpus(entire_text, "_2020_adv_verb_word_count.txt")
#gensim_analyze_corpus(boys, "_boys_word_count.txt")
#gensim_analyze_corpus(girls, "_girls_word_count.txt")


#for i in range(4):
#    fn = "_kkz{}_2020_words_count.txt".format(i)
#    gensim_analyze_corpus(lda_text[i], fn)

#print("Total {}, Train {}, Sample1 {}, Sample2 {}".format(len(entire_text), accum_cands, len(sample1_text), len(sample2_text)))

# Ignore values which did not accumulated any text
#accum_text = []
#for t in accum_train_text:
#    if not len(t) == 0:
#        accum_text.append(t)

#t_model = run_lda(accum_text, 4, False)
#if len(sample1_text) > 0:
#    apply_new_text_on_train_model(t_model, sample1_text, sample1_index2cand, "last30")
#if len(sample2_text) > 0:
#    apply_new_text_on_train_model(t_model, sample2_text, sample2_index2cand, "2")

#run_lda(lda_text[0], 0, 'lda0_backup')
#gensim_apply_text_on_model('lda0_backup', sample_text)

print(datetime.datetime.now())
print("Done")

#load_lda('my_lda_backup')

#high_d, high_l, id2word_h = gensim_analyze_corpus(high, "_high_grades.txt")
#low_d, low_l, id2word_l = gensim_analyze_corpus(low, "_low_grades.txt")

#for key in high_d:
#    if high_d[key] > 30:
#        word = id2word_h[key]
#        low_key = id2word_l.token2id[word]
#        if low_key in low_d:
#            ph = high_d[key] / len(high)
#            pl = low_d[low_key] / len(low)
#            if ph >= 1.8 * pl:
#                print("{}) {} ({:.5f}) VS  {} ({:.5f}) ".format(id2word_h[key], high_d[key], ph, low_d[low_key], pl))

#for i in range(4):
#    if len(lda_text[i]) > 0:
#        name = "_{}_high_grade.txt".format(NAMES[i])
#        print("{} size: {}".format(name, len(lda_text[i])))
#        gensim_analyze_corpus(lda_text[i], name)
