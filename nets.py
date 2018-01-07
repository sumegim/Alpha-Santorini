import tensorflow as tf

######################
#   HYPERPARAMETERS  #
######################
lr = 0.01
c = 0.0001
momentum = 0.9

board_size = 5
num_channels = 12

######################
#  HELPER FUNCTIONS  #
######################

def filter(in_channel, out_channel, kernel_size):
        return tf.Variable(initial_value=tf.contrib.layers.xavier_initializer(),
                           expected_shape = [kernel_size, kernel_size, in_channel, out_channel], 
                           name="filter"+str(in_channel)+str(out_channel), 
                           dtype=tf.float32)
        
def conv_block(features, f, activation_fn, phase, k):
    conv = tf.layers.conv2d(inputs=features, filters=f, kernel_size=[k, k], strides=[1, 1], padding="SAME")
    return tf.contrib.layers.batch_norm(conv, center=True, scale=True, is_training=phase, 
                                           updates_collections=None, activation_fn=activation_fn)
    
def res_block(features, in_channel, out_channel, kernel_size, phase):
    conv1 = conv_block(features, 256, tf.nn.relu, phase, kernel_size)
    conv2 = conv_block(conv1, out_channel, None, phase, kernel_size)    
    return tf.nn.relu(conv2+features)

#############
#  NETWORK  #
############

class deep_net():
    # initial conv layer
    def __init__(self, phase, scope, lr):
        with tf.variable_scope(scope):
            self.lr = lr
            self.phase = phase #whether training or not, for batch norm
            self.s_t_in = tf.placeholder(dtype=tf.float32, shape=[None, board_size, board_size, num_channels])
            self.tower0 = conv_block(self.s_t_in, 256, tf.nn.relu, self.phase, 3)
            
            # residual tower
            height = 9
            for x in range(height):
               previous = self.get_tower(x)
               setattr(self, 'tower'+str(x+1), res_block(previous, 256, 256, 3, self.phase))
            
            #policy head
            pre_p = conv_block(self.get_tower(height), 2, tf.nn.relu, self.phase, 1)
            self.pre_p = tf.contrib.layers.flatten(pre_p)
            self.p_w_illegal = tf.contrib.layers.fully_connected(self.pre_p, num_outputs=pow(board_size,2), activation_fn=None) 
            self.legal_moves = tf.placeholder(dtype=tf.float32, shape=[None, pow(board_size,2)])
            p = tf.multiply(self.p_w_illegal, self.legal_moves)
            self.p = tf.divide(p, tf.reduce_sum(p))  #doesn't use softmax because want to preserve 0's
            
            #value head
            pre_v = conv_block(self.get_tower(height), 1, tf.nn.relu, self.phase, 1)
            self.pre_v = tf.contrib.layers.flatten(pre_v)
            self.v = tf.contrib.layers.fully_connected(self.pre_v, num_outputs=1, activation_fn=tf.nn.tanh) 
    
            #reward signal and update
            self.z = tf.placeholder(dtype=tf.float32, shape=[None,1])
            self.pi = tf.placeholder(dtype=tf.float32, shape=[None,pow(board_size,2)])
            self.vars = tf.trainable_variables() 
            L2 = tf.add_n([tf.nn.l2_loss(w) for w in self.vars])
            self.loss = tf.transpose(tf.squared_difference(self.z,self.v)) - tf.nn.softmax_cross_entropy_with_logits(labels=self.pi,logits=self.p) + c*L2
            self.optimizer = tf.train.MomentumOptimizer(lr, momentum).minimize(self.loss)
       
    def get_tower(self, height):
        return getattr(self, 'tower'+str(height))
         
    def P(self, s, legal_moves, sess):
        feed_dict = {self.s_t_in:s, self.legal_moves:legal_moves}
        return sess.run(self.p, feed_dict=feed_dict)
        
    def evaluate(self, s, legal_moves, sess):
        feed_dict = {self.s_t_in:s, self.legal_moves:legal_moves}
        return sess.run(self.v, feed_dict=feed_dict)
    
    def P_and_v(self, s, legal_moves, sess):
        feed_dict = {self.s_t_in:s, self.legal_moves:legal_moves}
        return sess.run([self.p, self.v], feed_dict=feed_dict)
        
    def train(self, s, z, pi, legal_moves, sess):
        self.phase = True
        feed_dict = {self.s_t_in:s, self.z:z, self.pi:pi, self.legal_moves:legal_moves}
        _, loss = sess.run([self.optimizer, self.loss], feed_dict=feed_dict)
        self.phase = False
        return loss